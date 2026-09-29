"""A background task pool for slow, cacheable per-object work (DSS image fetching, orbit diagram
generation) that both the app and, eventually, a website generator need done for every eligible object -
not just the ones a user happens to view.

One worker thread drains the queue, one task at a time - deliberately not in parallel, to avoid hammering
the external DSS service and because matplotlib's global figure state is not safe to use from several
threads at once. `reset` replaces the queue wholesale (called at startup and after every Reload, with
tasks built from whatever is currently missing on disk); `add` queues a single further task between
Reloads; `bump` moves a task already in the queue to the front, so viewing an object in the app does not
have to wait behind the whole backlog. A TaskPool only knows about callables, string keys and a free-text
category per task - it is not tied to DSS or orbits, so
a future website generator can build and drain its own pool the same way; `progress()` breaks its
done/total counts down by category so a caller can report "DSS: 5/200, orbits: 3/140" rather than one
combined number.
"""
import datetime
import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaTask:
    """One unit of queued work for a TaskPool.

    :ivar key: unique and stable across a Reload - the cache file's path, as a string, works well
    :ivar category: a free-text label (e.g. "dss", "orbit") progress() breaks its counts down by
    :ivar run: fetches or generates the file; False means it did not work
    :ivar label: what it is for, in words (the Object, the pair): shown when the task fails
    :ivar failure: what a False return of `run` means
    """
    key: str
    category: str
    run: Callable[[], bool]
    label: str = ""
    failure: str = "the task did not produce its result"


@dataclass(frozen=True)
class TaskFailure:
    """A task of the current batch that did not work: it returned False or raised.

    :ivar key: the failed task's key
    :ivar category: the failed task's category
    :ivar label: the failed task's label
    :ivar message: why it failed
    :ivar time: when it failed
    """
    key: str
    category: str
    label: str
    message: str
    time: datetime.datetime = field(default_factory=datetime.datetime.now)


class TaskPool:
    """A single-worker-thread queue of MediaTasks: one task runs at a time, deliberately not in
    parallel (see the module docstring for why), with per-category progress and failure tracking that
    a Reload resets wholesale via `reset`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: deque[MediaTask] = deque()
        self._running: str | None = None  # the key currently being run, if any
        self._total: dict[str, int] = {}  # category -> tasks in the current batch (since the last reset)
        self._done: dict[str, int] = {}  # category -> of those, how many have finished (succeeded or failed)
        self._generation = 0  # bumped by every reset, so a task from an old batch never counts
        self._failures: list[TaskFailure] = []  # of the current batch, in the order they happened
        self._wakeup = threading.Event()
        self._thread: threading.Thread | None = None

    def reset(self, tasks: list[MediaTask]) -> None:
        """Replaces the queue with a fresh batch and resets progress for it; a task from the previous
        batch that is still running when this is called is let it finish, but does not count towards
        either batch's progress.

        :param tasks: the new batch of tasks
        """
        with self._lock:
            self._queue = deque(tasks)
            self._total = {}
            for task in tasks:
                self._total[task.category] = self._total.get(task.category, 0) + 1
            self._done = {category: 0 for category in self._total}
            self._failures = []
            self._generation += 1
        self._wakeup.set()

    def add(self, task: MediaTask, front: bool = False) -> bool:
        """Queues one more task without touching the rest of the batch, at the back or, with `front`, at the
        front - for work that turns up between Reloads, such as an Object whose position was just edited.
        It counts towards the current batch's progress.

        :param task: the task to queue
        :param front: whether to queue it at the front rather than the back
        :returns: False and does nothing when a task with the same key is already queued or running: the
            pending one will produce the same file
        """
        with self._lock:
            if self._running == task.key or any(t.key == task.key for t in self._queue):
                return False
            if front:
                self._queue.appendleft(task)
            else:
                self._queue.append(task)
            self._total[task.category] = self._total.get(task.category, 0) + 1
            self._done.setdefault(task.category, 0)
        self._wakeup.set()
        return True

    def progress(self) -> dict[str, tuple[int, int]]:
        """category -> (done, total) for the current batch; empty when nothing is queued. A category
        with nothing to do in this batch is left out entirely, rather than reported as (0, 0).

        :returns: the per-category progress of the current batch
        """
        with self._lock:
            return {category: (self._done[category], total) for category, total in self._total.items()}

    def failures(self) -> list[TaskFailure]:
        """The tasks of the current batch that failed so far. A Reload starts a new batch, and queues again what is
        still missing, so what keeps failing shows up again.

        :returns: the current batch's failures, in the order they happened
        """
        with self._lock:
            return list(self._failures)

    def is_pending(self, key: str) -> bool:
        """Whether a task with this key is queued or currently running - False both before it was ever
        queued and after it has finished (whether it then succeeded or failed); callers distinguish those
        two by checking the actual result (typically: does the file exist now) instead.

        :param key: the task key to check
        :returns: whether it is queued or running
        """
        with self._lock:
            return self._running == key or any(t.key == key for t in self._queue)

    def bump(self, keys: set[str]) -> None:
        """Moves every currently queued task whose key is in `keys` to the front, in their existing
        relative order; keys that are not queued (nothing missing, or not a DSS/orbit key) are ignored.

        :param keys: the task keys to move to the front
        """
        with self._lock:
            front = [t for t in self._queue if t.key in keys]
            if not front:
                return
            rest = [t for t in self._queue if t.key not in keys]
            self._queue = deque(front + rest)
        self._wakeup.set()

    def start(self) -> None:
        """Starts the single worker thread; safe to call more than once, only the first call starts it."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="media-task-pool")
        self._thread.start()

    def _run(self) -> None:
        """The worker thread's loop: runs tasks one at a time until the pool is destroyed, sleeping on
        `_wakeup` whenever the queue is empty."""
        while True:
            next_up = self._next()
            if next_up is None:
                self._wakeup.wait()
                self._wakeup.clear()
                continue
            task, generation = next_up
            failed = None
            try:
                if not task.run():
                    failed = task.failure
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # a task's own code (network, file I/O, image processing, ...) can raise anything; one
                # task failing this way must not kill the worker thread that processes the rest of the queue
                logger.exception("media task failed: %s", task.key)
                failed = f"{type(exc).__name__}: {exc}"
            finally:
                with self._lock:
                    self._running = None
                    if generation == self._generation:
                        self._done[task.category] += 1
                        if failed is not None:
                            self._failures.append(TaskFailure(task.key, task.category, task.label, failed))

    def _next(self) -> tuple[MediaTask, int] | None:
        """Pops the next queued task and marks it running, paired with the generation it belongs to so a
        reset mid-run does not let it count towards the wrong batch; None when the queue is empty."""
        with self._lock:
            if not self._queue:
                return None
            task = self._queue.popleft()
            self._running = task.key
            return task, self._generation
