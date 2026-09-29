# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""The app's shared state, started on a copy of a fixture data directory (the background tasks write into it)."""
import shutil
import sys
import tempfile
import time
from pathlib import Path

from faint_fuzzies.domain import dss, orbits
from faint_fuzzies.ui.state import AppState

sys.path.insert(0, str(Path(__file__).parent))
from OrbitChecks import orbits_file_text  # noqa: E402


def background_work_of_state(fixture, fetch_dss, generate_orbits):
    """Starts an AppState on a copy of the data directory `fixture`, given an orbit file for the pair STF999 of its
    WDS, with the DSS fetch and the orbit drawing stubbed (they count their calls and fail, so nothing goes to the
    network or is drawn), gives the background pool a moment, and returns {"dss_calls", "orbit_calls", "queued": the
    categories in the pool, "written": image files found under dss/ and orbits/}."""
    dss_calls, orbit_calls = [], []
    original = dss.fetch_dss_image_by_coordinates, orbits.generate_orbit_diagram
    dss.fetch_dss_image_by_coordinates = lambda *args, **kwargs: dss_calls.append(args) or False
    orbits.generate_orbit_diagram = lambda *args, **kwargs: orbit_calls.append(args) or False
    folder = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(fixture, folder / "data")
        (folder / "data" / "catalogues" / "orbits.txt").write_text(
            orbits_file_text([("WDS11111+2222", "STF 999", "y")]), encoding="utf-8")
        state = AppState(folder / "data", None, fetch_dss=fetch_dss, generate_orbits=generate_orbits)
        wanted = (1 if fetch_dss else 0) + (1 if generate_orbits else 0)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(dss_calls) + len(orbit_calls) < wanted:
            time.sleep(0.05)
        time.sleep(0.3)
        written = sum(len(list((folder / "data" / name).rglob("*.jpg"))) for name in ("dss", "orbits")
                      if (folder / "data" / name).exists())
        return {"dss_calls": len(dss_calls), "orbit_calls": len(orbit_calls),
                "queued": sorted(state.task_pool.progress()), "written": written}
    finally:
        dss.fetch_dss_image_by_coordinates, orbits.generate_orbit_diagram = original
        shutil.rmtree(folder, ignore_errors=True)
