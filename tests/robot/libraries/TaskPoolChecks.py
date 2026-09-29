# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
import threading
import time

from faint_fuzzies.tasks import MediaTask, TaskPool


def _wait_until(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


def run_added_tasks():
    """Blocks the worker on a first task, then adds: one at the back, one at the front, a duplicate of the
    first, one more at the back, and a duplicate of the running task. Releases the worker and returns what
    add returned, the order the tasks ran in and the progress before and after."""
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
    return {"returned": returned, "order": order, "before": before, "after": pool.progress()}


def run_failing_tasks():
    """Runs a task that returns False, one that raises, and one that works, and returns the failures the pool
    recorded as (key, category, label, message); then resets the pool, which starts a batch without failures."""
    pool = TaskPool()

    def raises():
        raise RuntimeError("boom")

    pool.reset([MediaTask("no-result", "dss", lambda: False, "M 13 (objects.json)", "no DSS image could be fetched"),
                MediaTask("raised", "orbit", raises, "STF 1 AB"),
                MediaTask("fine", "dss", lambda: True, "M 31")])
    pool.start()
    _wait_until(lambda: pool.progress().get("dss") == (2, 2) and pool.progress().get("orbit") == (1, 1))
    found = [(f.key, f.category, f.label, f.message) for f in pool.failures()]
    pool.reset([])
    return {"failures": found, "after_reset": pool.failures()}
