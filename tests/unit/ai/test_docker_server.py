"""Ollama in a container ([ai.docker]) and downloading its models, with the fake engine and server of
tests/unit/ai/fake_ollama.py on a free local port."""
import socket

import pytest

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.docker_server import running_container
from faint_fuzzies.ai.ollama import ensure_model
from faint_fuzzies.ai.server import running_server
from faint_fuzzies.config import AiConfig, DockerConfig
from tests.unit.ai.fake_ollama import FakeContainer, FakeEngine, FakeOllama


@pytest.fixture
def port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def ollama(port):
    server = FakeOllama(port, models=["bge-m3:latest"])
    yield server
    server.stop()


def settings(port, **docker):
    return AiConfig(f"http://localhost:{port}/v1", "chat", "bge-m3", startup_timeout=2,
                    docker=DockerConfig(**docker))


def test_a_missing_container_is_created_from_the_config_and_its_image_pulled(port, ollama):
    engine = FakeEngine(ollama)
    config = settings(port, image="ollama/ollama:rocm", gpu="amd", env=(("HSA_OVERRIDE_GFX_VERSION", "10.3.0"),))
    with running_container(config, engine=engine):
        assert AiClient(config.url, 2).answers()
    assert engine.pulled == ["ollama/ollama:rocm"]
    assert engine.created == {
        "image": "ollama/ollama:rocm", "detach": True,
        "ports": {"11434/tcp": ("127.0.0.1", port)},
        "volumes": {"ollama": {"bind": "/root/.ollama", "mode": "rw"}},
        "environment": {"HSA_OVERRIDE_GFX_VERSION": "10.3.0"},
        "devices": ["/dev/kfd:/dev/kfd:rwm", "/dev/dri:/dev/dri:rwm"],
    }


def test_an_image_that_is_there_is_not_pulled_again(port, ollama):
    engine = FakeEngine(ollama, images=["ollama/ollama"])
    with running_container(settings(port), engine=engine):
        pass
    assert engine.pulled == []
    assert "devices" not in engine.created and "device_requests" not in engine.created


def test_an_nvidia_gpu_is_asked_for_with_a_device_request(port, ollama):
    engine = FakeEngine(ollama, images=["ollama/ollama"])
    with running_container(settings(port, gpu="nvidia"), engine=engine):
        pass
    assert [request.capabilities for request in engine.created["device_requests"]] == [[["gpu"]]]


def test_a_stopped_container_is_started_for_the_block_and_stopped_after_it(port, ollama):
    container = FakeContainer("ollama", ollama, status="exited")
    engine = FakeEngine(ollama, container=container)
    with running_container(settings(port), engine=engine):
        assert container.status == "running"
    assert container.calls == ["start", "stop"]
    assert engine.created is None


def test_a_running_container_is_used_and_left_running(port, ollama):
    ollama.start()
    container = FakeContainer("ollama", ollama, status="running")
    with running_container(settings(port), engine=FakeEngine(ollama, container=container)):
        pass
    assert container.calls == []
    assert AiClient(f"http://localhost:{port}/v1", 2).answers()


def test_a_container_that_stops_before_it_answers_shows_its_last_lines(port, ollama):
    container = FakeContainer("ollama", ollama, crash=True)
    with (pytest.raises(AiError, match="stopped .exited.*\n.*no compatible GPUs"),
          running_container(settings(port), engine=FakeEngine(ollama, container=container))):
        pass


def test_a_model_the_server_has_under_its_latest_tag_is_not_pulled(port, ollama):
    ollama.start()
    ensure_model(f"http://localhost:{port}/v1", "bge-m3", 2, None)
    assert ollama.pulled == []


def test_a_missing_model_is_pulled_with_its_progress(port, ollama):
    ollama.start()
    progress = []
    ensure_model(f"http://localhost:{port}/v1", "qwen3:8b", 2, lambda step, done: progress.append((step, done)))
    assert ollama.pulled == ["qwen3:8b"]
    assert progress == [("downloading the model qwen3:8b", 0.5)]


def test_a_model_that_cannot_be_pulled_is_an_error(port, ollama):
    ollama.start()
    with pytest.raises(AiError, match="cannot download unknown: pull model manifest"):
        ensure_model(f"http://localhost:{port}/v1", "unknown", 2, None)


def test_running_server_with_docker_starts_the_container_and_pulls_the_models(port, ollama, tmp_path, monkeypatch):
    engine = FakeEngine(ollama, images=["ollama/ollama"])
    monkeypatch.setattr("faint_fuzzies.ai.docker_server.docker_client", lambda: engine)
    with running_server(settings(port), tmp_path, models=("nomic-embed-text",)):
        assert ollama.pulled == ["nomic-embed-text"]
    assert engine.container.calls == ["start", "stop"]
