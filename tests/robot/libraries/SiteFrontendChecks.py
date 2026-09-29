# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""AppState.build_site, GlobalPages built from already-loaded data, and SiteServer - all without a browser."""
import socket
import subprocess
from datetime import date
from pathlib import Path

from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from faint_fuzzies.site.build import GlobalPages
from faint_fuzzies.site.server import SiteServer, _free_port
from faint_fuzzies.ui.state import AppState

_DATE = date(2026, 9, 16)


def rendered_page_matches_a_fresh_load(data_dir):
    """The home page rendered by a GlobalPages built from already-loaded data (as AppState.build_site does)
    is byte-identical to one that loads the data directory itself."""
    root = Path(data_dir)
    static = load_static_catalogues(root)
    data = load_data_dir(root, static)
    reused = GlobalPages(root, static=static, data=data, optic_names={}, last_update=_DATE)
    fresh = GlobalPages(root, last_update=_DATE)
    return reused.render_home("en") == fresh.render_home("en")


def build_via_app_state(data_dir, output_dir):
    """AppState.build_site: no network or drawing work, since fetch_dss/generate_orbits are both off."""
    state = AppState(Path(data_dir), fetch_dss=False, generate_orbits=False)
    progress = []
    report = state.build_site(Path(output_dir), lambda step, fraction: progress.append((step, fraction)))
    return {"report": report, "progress_steps": len(progress) > 0}


def build_again_after_removing_an_object(data_dir, output_dir, objects_json_text):
    """Writes `objects_json_text` over the own catalogue (removing whatever it leaves out) and builds again,
    with prune=True (the Site page's "Prune" checkbox) - a second, independent AppState, since the first
    already loaded the old catalogue into memory."""
    root = Path(data_dir)
    (root / "observations" / "owner" / "objects.json").write_text(objects_json_text, encoding="utf-8")
    state = AppState(root, fetch_dss=False, generate_orbits=False)
    return state.build_site(Path(output_dir), prune=True)


def free_port_is_bindable():
    port = _free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
    return port > 0


def site_server_reports_a_clear_error_when_the_executable_is_missing():
    server = SiteServer(executable="definitely-not-a-real-executable-xyz")
    server.ensure_running(Path("/tmp"))
    result = {"url": server.url, "has_error": server.error is not None, "process_is_none": server.process is None}
    server.stop()
    return result


def site_server_url_reflects_a_running_process():
    """Simulates "already running" with a real, harmless subprocess, and checks ensure_running is then a
    no-op (the port is not reassigned) before stopping it again."""
    server = SiteServer()
    server.process = subprocess.Popen(["sleep", "30"])
    server.port = 12345
    server.ensure_running(Path("/tmp"))
    result = {"url": server.url, "port_unchanged": server.port == 12345}
    server.stop()
    result["stopped"] = server.process is None
    return result
