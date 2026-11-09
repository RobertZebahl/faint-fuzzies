"""TaskPool (tasks.py): one task added between Reloads, at the back or the front, counted in the progress, and
ignored when its key is already queued or running; failed tasks are recorded until the next Reload."""
import threading
import time

from faint_fuzzies.tasks import MediaTask, TaskPool


def _wait_until(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


def test_add_queues_one_task_without_replacing_the_batch():
    """The worker is blocked on a first task while the test adds one at the back, one at the front, a duplicate of
    the first, one more at the back, and a duplicate of the running task."""
    pool = TaskPool()
    order = []
    gate = threading.Event()
    started = threading.Event()

    def blocker():
        started.set()
        gate.wait(5)
        return True

    def make(key):
        return MediaTask(key, "dss", lambda: order.append(key) or True)

    pool.reset([MediaTask("blocker", "dss", blocker)])
    pool.start()
    started.wait(5)
    returned = [pool.add(make("back")), pool.add(make("front"), front=True), pool.add(make("back")),
                pool.add(make("third")), pool.add(MediaTask("blocker", "dss", lambda: True))]
    before = pool.progress()
    gate.set()
    _wait_until(lambda: len(order) == 3 and pool.progress().get("dss") == (4, 4))
    assert returned == [True, True, False, True, False]
    assert order == ["front", "back", "third"]
    assert before == {"dss": (0, 4)}
    assert pool.progress() == {"dss": (4, 4)}


def test_a_task_that_returns_false_or_raises_is_recorded_as_a_failure():
    """With what it was for and what happened; a task that works is not, and a Reload (reset) starts again."""
    pool = TaskPool()

    def raises():
        raise RuntimeError("boom")

    pool.reset([MediaTask("no-result", "dss", lambda: False, "M 13 (objects.json)", "no DSS image could be fetched"),
                MediaTask("raised", "orbit", raises, "STF 1 AB"),
                MediaTask("fine", "dss", lambda: True, "M 31")])
    pool.start()
    _wait_until(lambda: pool.progress().get("dss") == (2, 2) and pool.progress().get("orbit") == (1, 1))
    assert [(f.key, f.category, f.label, f.message) for f in pool.failures()] == [
        ("no-result", "dss", "M 13 (objects.json)", "no DSS image could be fetched"),
        ("raised", "orbit", "STF 1 AB", "RuntimeError: boom")]
    pool.reset([])
    assert not pool.failures()
