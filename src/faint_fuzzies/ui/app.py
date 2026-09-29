"""Entry point for "faint-fuzzies serve": a local, single-user web app over one data directory."""
from pathlib import Path

from nicegui import app as nicegui_app
from nicegui import ui
from starlette.requests import Request

from faint_fuzzies.loading import step_reporter
from faint_fuzzies.ui.browse import build as build_browse
from faint_fuzzies.ui.log import build as build_log
from faint_fuzzies.ui.media import mount_static_media
from faint_fuzzies.ui.site import build as build_site
from faint_fuzzies.ui.state import AppState
from faint_fuzzies.ui.statistics import build as build_statistics


def run_app(data_dir: Path, port: int, fetch_dss: bool = True, generate_orbits: bool = True) -> None:
    """Builds the app's state and pages, then runs the NiceGUI server until stopped. Blocks until shutdown.

    :param data_dir: the data directory the app serves
    :param port: the local port to listen on
    :param fetch_dss: whether to fetch missing DSS images on load (see AppState)
    :param generate_orbits: whether to generate missing orbit diagrams on load (see AppState)
    """
    state = AppState(data_dir, step_reporter(), fetch_dss, generate_orbits)
    mount_static_media(data_dir)
    nicegui_app.on_shutdown(state.site_server.stop)  # the Site page's PHP preview server, if it was ever started

    @ui.page("/")
    def index(request: Request) -> None:
        # `?object=objects.json:494` opens Browse on that Object (the links of the Log page)
        build_browse(state, request.query_params.get("object"))

    @ui.page("/statistics")
    def statistics() -> None:
        build_statistics(state)

    @ui.page("/log")
    def log() -> None:
        build_log(state)

    @ui.page("/site")
    def site() -> None:
        build_site(state)

    favicon = Path(__file__).parent / "favicon.ico"
    ui.run(host="127.0.0.1", port=port, title="Faint Fuzzies", favicon=favicon, reload=False, show=False)
