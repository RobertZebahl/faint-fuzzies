"""A local PHP dev server the app can spawn to preview the built website (see ui/site.py) - kept here, not
under ui/, so it has no NiceGUI dependency and can be exercised directly.

One `SiteServer` per app run: `ensure_running` starts the process the first time it is called and does nothing
on later calls, whether they follow an earlier success or an earlier failure - `state.build_site` always calls
it again after a build, so a php that only became available on PATH later gets another chance next time. It is
pointed at the output folder once and then just keeps serving whatever is currently on disk, so a later build
(which writes into that same folder in place) never needs the process restarted.
"""
import socket
import subprocess
from pathlib import Path


class SiteServer:
    """One `SiteServer` per app run: `ensure_running` starts the process the first time it is called and
    does nothing on later calls, whether they follow an earlier success or an earlier failure -
    `state.build_site` always calls it again after a build, so a php that only became available on PATH
    later gets another chance next time. It is pointed at the output folder once and then just keeps
    serving whatever is currently on disk, so a later build (which writes into that same folder in place)
    never needs the process restarted.

    :param executable: the php executable to run; only ever overridden by tests, to force the "not found"
        path deterministically regardless of whether php happens to be installed where the tests run
    """
    def __init__(self, executable: str = "php") -> None:
        self._executable = executable
        self.process: subprocess.Popen | None = None
        self.port: int | None = None
        self.error: str | None = None

    def ensure_running(self, output_dir: Path) -> None:
        """Starts `php -S 127.0.0.1:<a free port> -t output_dir` if nothing is running yet. `error` is cleared
        on success and set to a message for the Site page on failure (most likely: no `php` on PATH).

        :param output_dir: the folder the server serves
        """
        if self.process is not None and self.process.poll() is None:
            return
        self.process = None
        self.port = _free_port()
        try:
            self.process = subprocess.Popen(
                [self._executable, "-S", f"127.0.0.1:{self.port}", "-t", str(output_dir)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.error = None
        except OSError as exc:
            self.port = None
            self.error = f"could not start the local PHP server: {exc}"

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process = None

    @property
    def url(self) -> str | None:
        return f"http://127.0.0.1:{self.port}/" if self.process is not None else None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
