"""Starting the model server on demand, with Python's own http.server standing in for it (any HTTP answer, even
its 404 for /v1/models, counts as a server that answers) and small Python one-liners for servers that fail."""
import socket
import sys

import pytest

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.server import LOG_NAME, running_server
from faint_fuzzies.config import AiConfig


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def config(port, command, **settings):
    return AiConfig(f"http://127.0.0.1:{port}/v1", "chat", "model", command=tuple(command), **settings)


def http_server(port):
    return [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]


def test_a_server_is_started_for_the_block_and_stopped_after_it(tmp_path):
    port = free_port()
    settings = config(port, http_server(port))
    started = []
    with running_server(settings, tmp_path, lambda step, _done: started.append(step)):
        assert AiClient(settings.url, 5).answers()
    assert not AiClient(settings.url, 5).answers()
    assert started and (tmp_path / LOG_NAME).is_file()


def test_a_server_that_already_answers_is_used_and_left_running(tmp_path):
    port = free_port()
    with running_server(config(port, http_server(port)), tmp_path / "first"):
        marker = tmp_path / "started"
        command = [sys.executable, "-c", f"open({str(marker)!r}, 'w')"]
        with running_server(config(port, command), tmp_path / "second"):
            pass
        assert not marker.exists()
        assert AiClient(f"http://127.0.0.1:{port}/v1", 5).answers()


def test_without_a_command_nothing_is_started(tmp_path):
    with running_server(config(free_port(), []), tmp_path):
        pass
    assert not (tmp_path / LOG_NAME).exists()


def test_a_command_that_ends_before_the_server_answers_points_to_its_log(tmp_path):
    command = [sys.executable, "-c", "import sys; print('no GPU found'); sys.exit(3)"]
    with pytest.raises(AiError, match=r"ended \(exit code 3\).*server.log"), running_server(config(free_port(), command), tmp_path):
        pass
    assert "no GPU found" in (tmp_path / LOG_NAME).read_text()


def test_a_server_that_never_answers_is_given_up_on_and_stopped(tmp_path):
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(AiError, match="did not answer .* within 0.5 s"), running_server(config(free_port(), command, startup_timeout=0.5), tmp_path):
        pass


def test_a_command_that_does_not_exist_is_an_error(tmp_path):
    with pytest.raises(AiError, match="cannot start the model server"), running_server(config(free_port(), [str(tmp_path / "no-such-program")]), tmp_path):
        pass


def test_the_command_gets_the_configured_environment(tmp_path):
    port = free_port()
    script = (f"import os, sys; open({str(tmp_path / 'env')!r}, 'w').write(os.environ['GFX']); "
              f"sys.argv = ['x', '{port}', '--bind', '127.0.0.1']; import runpy; "
              f"runpy.run_module('http.server', run_name='__main__')")
    with running_server(config(port, [sys.executable, "-c", script], env=(("GFX", "10.3.0"),)), tmp_path):
        pass
    assert (tmp_path / "env").read_text() == "10.3.0"
