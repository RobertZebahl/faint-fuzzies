"""How many CPUs the program uses for work on several threads (cpus.py): what the machine has and allows, less the
limit of a container (`docker run --cpus=2` sets a quota that the CPU count does not show). Nothing is a fixed number.
"""
import os

import pytest

from faint_fuzzies.cpus import usable_cpus


def _cpus_with_cgroup(folder, v2=None, v1_quota=None, v1_period="100000"):
    """`usable_cpus` for a cgroup folder made here: a v2 `cpu.max` with the given text, or the v1 files."""
    if v2 is not None:
        (folder / "cpu.max").write_text(v2)
    if v1_quota is not None:
        (folder / "cpu").mkdir()
        (folder / "cpu" / "cpu.cfs_quota_us").write_text(str(v1_quota))
        (folder / "cpu" / "cpu.cfs_period_us").write_text(str(v1_period))
    return usable_cpus(folder)


@pytest.fixture
def machine(tmp_path):
    """What the machine and the system allow, without any container limit (there is no cgroup folder)."""
    return usable_cpus(tmp_path / "no-such-cgroup-folder")


def test_the_machine_decides(machine):
    assert 1 <= machine <= os.cpu_count()


@pytest.mark.parametrize("cgroup", [{"v2": "max 100000"}, {"v1_quota": -1}], ids=["v2", "v1"])
def test_no_quota_changes_nothing(tmp_path, machine, cgroup):
    assert _cpus_with_cgroup(tmp_path, **cgroup) == machine


@pytest.mark.parametrize(("cgroup", "limit"), [
    pytest.param({"v2": "200000 100000"}, 2, id="2 CPUs of quota"),
    pytest.param({"v2": "150000 100000"}, 2, id="1.5 rounds up to 2"),
    pytest.param({"v2": "10000 100000"}, 1, id="at least 1"),
    pytest.param({"v1_quota": 200000}, 2, id="v1"),
])
def test_a_quota_of_a_container_limits_it(tmp_path, machine, cgroup, limit):
    assert _cpus_with_cgroup(tmp_path, **cgroup) == min(machine, limit)


def test_a_quota_above_the_machine_does_not_add_cpus(tmp_path, machine):
    assert _cpus_with_cgroup(tmp_path, v2="6400000 100000") == machine


@pytest.mark.parametrize("text", ["abc def", ""], ids=["garbage", "empty"])
def test_a_quota_that_cannot_be_read_is_ignored(tmp_path, machine, text):
    assert _cpus_with_cgroup(tmp_path, v2=text) == machine
