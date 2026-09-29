# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
import os
import tempfile
from pathlib import Path

from faint_fuzzies.cpus import usable_cpus


def cpus_with_cgroup(v2=None, v1_quota=None, v1_period="100000"):
    """`usable_cpus` for a cgroup folder made here: a v2 `cpu.max` with the given text, or the v1 files."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        if v2 is not None:
            (root / "cpu.max").write_text(v2)
        if v1_quota is not None:
            (root / "cpu").mkdir()
            (root / "cpu" / "cpu.cfs_quota_us").write_text(str(v1_quota))
            (root / "cpu" / "cpu.cfs_period_us").write_text(str(v1_period))
        return usable_cpus(root)


def cpus_of_the_machine():
    """What the machine and the system allow, without any container limit (there is no cgroup folder here)."""
    return usable_cpus(Path(tempfile.gettempdir()) / "no-such-cgroup-folder")


def logical_cpus():
    return os.cpu_count()
