"""The local PHP preview server of the app's Site page (site/server.py)."""
import socket
import subprocess

from faint_fuzzies.site.server import SiteServer, _free_port


def test_a_free_port_can_actually_be_bound():
    port = _free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
    assert port > 0


def test_siteserver_reports_a_clear_error_when_the_executable_is_missing(tmp_path):
    server = SiteServer(executable="definitely-not-a-real-executable-xyz")
    server.ensure_running(tmp_path)
    try:
        assert server.error is not None
        assert server.process is None
        assert server.url is None
    finally:
        server.stop()


def test_siteserver_does_not_restart_an_already_running_process(tmp_path):
    """A harmless process stands in for a running server."""
    server = SiteServer()
    server.process = subprocess.Popen(["sleep", "30"])
    server.port = 12345
    try:
        server.ensure_running(tmp_path)
        assert server.url == "http://127.0.0.1:12345/"
        assert server.port == 12345
    finally:
        server.stop()
    assert server.process is None
