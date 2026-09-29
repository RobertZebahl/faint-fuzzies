"""Lets a `faint-fuzzies` subprocess spawned by a Robot test (see resources/cli.resource's `Run CLI`) measure
its own code coverage, the same as the `robot` process itself - see the README's "Code coverage" section.

Python imports a module named `sitecustomize` at interpreter startup if one is importable - this directory
is put on `PYTHONPATH` for exactly that reason, nothing else. `coverage.process_startup()` is always safe to
call: it is a no-op unless `COVERAGE_PROCESS_START` is set, so this has no effect when coverage is not asked
for, and does not need its own import guard.
"""
import coverage

coverage.process_startup()
