"""Starting the model server on demand: when nothing answers at [ai].url and [ai].command is set, the server is
started for as long as it is needed and stopped afterwards. A server that was already running is used as it is
and never stopped - only the one started here is."""
import os
import signal
import subprocess
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.config import AiConfig

LOG_NAME = "server.log"
POLL_SECONDS = 0.25
STOP_SECONDS = 10.0


@contextmanager
def running_server(config: AiConfig, log_dir: Path,
                   on_start: Callable[[str], None] | None = None) -> Generator[None]:
    """Makes sure a server answers at `config.url` inside the block.

    Without `config.command`, nothing is started: a missing server shows when the first request fails.

    :param config: the AI settings
    :param log_dir: where the started server's output goes (LOG_NAME, overwritten on every start)
    :param on_start: called with a message when the server has to be started
    :raises AiError: when the command cannot be run, ends before the server answers, or the server does not
        answer within `config.startup_timeout`
    """
    client = AiClient(config.url, config.timeout)
    if not config.command or client.answers():
        yield
        return
    if on_start:
        on_start(f"starting the model server ({' '.join(config.command)})")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_NAME
    with log_path.open("wb") as log:
        try:
            process = subprocess.Popen(config.command, env=os.environ | dict(config.env), stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as exc:
            raise AiError(f"cannot start the model server with {config.command[0]}: {exc.strerror}") from exc
        try:
            _wait_until_it_answers(client, process, config.startup_timeout, log_path)
            yield
        finally:
            _stop(process)


def _wait_until_it_answers(client: AiClient, process: subprocess.Popen, timeout: float, log_path: Path) -> None:
    deadline = time.monotonic() + timeout
    while not client.answers():
        if process.poll() is not None:
            raise AiError(f"the model server ended (exit code {process.returncode}) before it answered at "
                          f"{client.url}; see {log_path}")
        if time.monotonic() > deadline:
            raise AiError(f"the model server did not answer at {client.url} within {timeout:g} s; see {log_path}")
        time.sleep(POLL_SECONDS)


def _stop(process: subprocess.Popen) -> None:
    """Stops the server the way Ctrl+C would, and kills it when it does not end in time."""
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(STOP_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
