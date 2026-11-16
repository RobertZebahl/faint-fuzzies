"""`serve --no-dss-fetch` and `serve --no-orbits-generation`: AppState then queues no DSS image or no orbit
diagram in the background, so the data directory is left as it is. Fixture "site_datadir", in a copy, with an orbit
file for its pair STF999. Both jobs are stubbed: they count their calls and fail, so nothing goes to the network or
is drawn."""
import shutil
import time

import pytest

from faint_fuzzies.domain import dss, orbits
from faint_fuzzies.ui.state import AppState
from tests.unit.builders import FIXTURES, orbits_file_text


@pytest.fixture
def calls(monkeypatch):
    found = {"dss": 0, "orbit": 0}

    def count(kind):
        def stub(*args, **kwargs):
            found[kind] += 1
            return False
        return stub

    monkeypatch.setattr(dss, "fetch_dss_image_by_coordinates", count("dss"))
    monkeypatch.setattr(orbits, "generate_orbit_diagram", count("orbit"))
    return found


def _background_work(tmp_path, fetch_dss, generate_orbits):
    """Starts an AppState and waits until its pool has run every queued task (so none runs after the stubs are
    gone); returns the categories queued and the number of images written under dss/ and orbits/."""
    root = tmp_path / "data"
    shutil.copytree(FIXTURES / "site_datadir", root)
    (root / "catalogues" / "orbits.txt").write_text(orbits_file_text([("WDS11111+2222", "STF 999", "y")]),
                                                    encoding="utf-8")
    pool = AppState(root, None, fetch_dss=fetch_dss, generate_orbits=generate_orbits).task_pool
    deadline = time.monotonic() + 5
    while any(done < total for done, total in pool.progress().values()):
        assert time.monotonic() < deadline, "the background tasks did not finish"
        time.sleep(0.05)
    written = sum(len(list((root / name).rglob("*.jpg"))) for name in ("dss", "orbits") if (root / name).exists())
    return sorted(pool.progress()), written


def test_the_app_fetches_dss_images_and_draws_orbits_by_default(tmp_path, calls):
    queued, _written = _background_work(tmp_path, True, True)
    assert queued == ["dss", "orbit"]
    assert calls["dss"] > 0
    assert calls["orbit"] > 0


def test_no_dss_image_is_queued_or_fetched_without_the_dss_switch(tmp_path, calls):
    queued, _written = _background_work(tmp_path, False, True)
    assert queued == ["orbit"]
    assert calls["dss"] == 0
    assert calls["orbit"] > 0


def test_no_orbit_diagram_is_queued_or_drawn_without_the_orbit_switch(tmp_path, calls):
    queued, _written = _background_work(tmp_path, True, False)
    assert queued == ["dss"]
    assert calls["orbit"] == 0
    assert calls["dss"] > 0


def test_with_both_switches_nothing_runs_and_nothing_is_written(tmp_path, calls):
    queued, written = _background_work(tmp_path, False, False)
    assert queued == []
    assert calls == {"dss": 0, "orbit": 0}
    assert written == 0
