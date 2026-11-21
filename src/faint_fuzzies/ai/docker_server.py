"""Ollama in a Docker container ([ai.docker]): created from the config when it does not exist yet, started when
it is not running, and stopped again afterwards - only when it was started here, and not with keep_running.

A container is created once and then reused as it is: a changed image, GPU or env in the config only takes
effect after the container is removed (`docker rm faint-fuzzies-ollama`); the models survive that in their volume.
"""
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.config import AiConfig, local_port

OLLAMA_PORT = "11434/tcp"
MODELS_PATH = "/root/.ollama"
POLL_SECONDS = 0.25
STOP_SECONDS = 10
LOG_LINES = 30


def docker_client() -> Any:
    """The Docker engine of this machine, as the environment (DOCKER_HOST) or the default socket names it.

    :raises AiError: when the `docker` package is missing or no engine answers
    """
    try:
        import docker
        import docker.errors
    except ImportError as exc:
        raise AiError("[ai.docker] needs the 'ai' extra (pip install 'faint-fuzzies[ai]')") from exc
    try:
        return docker.from_env()
    except docker.errors.DockerException as exc:
        raise AiError(f"cannot reach Docker: {exc}") from exc


@contextmanager
def running_container(config: AiConfig, on_progress: Callable[[str, float], None] | None = None,
                      engine: Any = None) -> Generator[None]:
    """Makes sure the container of `config.docker` runs and its server answers at `config.url` inside the block.

    :param config: the AI settings, with an [ai.docker] table
    :param on_progress: told what is being done (pulling the image, starting the container)
    :param engine: the Docker engine; docker_client() when not given
    :raises AiError: when Docker fails, or the server does not answer within `config.startup_timeout`
    """
    assert config.docker is not None
    engine = engine or docker_client()
    import docker.errors
    try:
        container = _container(engine, config, on_progress)
        container.reload()
        started = container.status != "running" and not config.docker.keep_running
        if container.status != "running":
            if on_progress:
                on_progress(f"starting the container {config.docker.container}", 0.0)
            container.start()
    except docker.errors.DockerException as exc:
        raise AiError(f"Docker failed: {exc}") from exc
    try:
        _wait_until_it_answers(AiClient(config.url, config.timeout), container, config.startup_timeout)
        yield
    finally:
        if started:
            try:
                container.stop(timeout=STOP_SECONDS)
            except docker.errors.DockerException:
                pass  # it may already be gone; there is nothing left to clean up then


def _container(engine: Any, config: AiConfig, on_progress: Callable[[str, float], None] | None) -> Any:
    """The container by its name, created first when there is none."""
    import docker.errors
    settings = config.docker
    assert settings is not None
    try:
        return engine.containers.get(settings.container)
    except docker.errors.NotFound:
        pass
    try:
        engine.images.get(settings.image)
    except docker.errors.ImageNotFound:
        if on_progress:
            on_progress(f"downloading the image {settings.image}", 0.0)
        engine.images.pull(settings.image)
    return engine.containers.create(settings.image, name=settings.container, detach=True,
                                    ports={OLLAMA_PORT: ("127.0.0.1", local_port(config))},
                                    volumes={settings.volume: {"bind": MODELS_PATH, "mode": "rw"}},
                                    environment=dict(settings.env), **_gpu_options(settings.gpu))


def _gpu_options(gpu: str) -> dict[str, Any]:
    if gpu == "amd":
        return {"devices": ["/dev/kfd:/dev/kfd:rwm", "/dev/dri:/dev/dri:rwm"]}
    if gpu == "nvidia":
        import docker.types
        return {"device_requests": [docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]}
    return {}


def _wait_until_it_answers(client: AiClient, container: Any, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while not client.answers():
        container.reload()
        if container.status not in ("created", "running", "restarting"):
            logs = container.logs(tail=LOG_LINES).decode("utf-8", "replace").strip()
            raise AiError(f"the container {container.name} stopped ({container.status}) before its server "
                          f"answered at {client.url}; its last lines:\n{logs}")
        if time.monotonic() > deadline:
            raise AiError(f"the container {container.name} did not answer at {client.url} within {timeout:g} s; "
                          f"see `docker logs {container.name}`")
        time.sleep(POLL_SECONDS)
