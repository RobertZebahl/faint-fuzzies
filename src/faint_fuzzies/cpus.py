"""How many CPUs this process can use, for work that is split over threads. Nothing here is fixed: it asks the machine
and, in a container, the limits set for the container."""
import math
import os
from pathlib import Path

CGROUP = Path("/sys/fs/cgroup")


def usable_cpus(cgroup: Path = CGROUP) -> int:
    """The number of CPUs the process may run on, at least 1.

    That is the logical CPUs of the machine (with hyper-threading twice the cores), less what the system keeps from
    the process: its affinity (Linux: `taskset`, cpusets; Python 3.13 asks for it itself), and the CPU quota of a
    container (cgroup v2 `cpu.max` or v1 `cpu.cfs_quota_us`, as set by `docker run --cpus=2`), which the other
    numbers do not show.

    :param cgroup: the cgroup filesystem root to read the container's CPU quota from
    :returns: the number of usable CPUs, at least 1
    """
    if hasattr(os, "process_cpu_count"):
        count = os.process_cpu_count() or 1
    elif hasattr(os, "sched_getaffinity"):
        count = len(os.sched_getaffinity(0))
    else:
        count = os.cpu_count() or 1
    quota = _quota(cgroup)
    return max(1, min(count, quota) if quota else count)


def _quota(cgroup: Path) -> int | None:
    """The CPUs a container's quota allows (rounded up), or None when there is no quota, or it cannot be read.

    :param cgroup: the cgroup filesystem root
    :returns: the quota in whole CPUs, or None when there is none, or it cannot be read
    """
    try:
        if (cgroup / "cpu.max").is_file():  # v2: "max 100000" or "<quota> <period>"
            quota, period = (cgroup / "cpu.max").read_text().split()[:2]
        else:  # v1
            quota = (cgroup / "cpu" / "cpu.cfs_quota_us").read_text().strip()
            period = (cgroup / "cpu" / "cpu.cfs_period_us").read_text().strip()
        return math.ceil(int(quota) / int(period)) if int(quota) > 0 else None
    except (OSError, ValueError, ZeroDivisionError):
        return None  # "max" (v2) is no number, and -1 (v1) no quota
