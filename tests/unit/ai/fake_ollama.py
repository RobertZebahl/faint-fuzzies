"""A tiny stand-in for Ollama in a thread: the OpenAI-compatible /v1/models, and Ollama's own /api/tags and a
streaming /api/pull (a model named "unknown" cannot be pulled) - plus a fake Docker engine whose container runs
it while started."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import docker


class FakeOllama:
    """:ivar models: the models it has; :ivar pulled: the models pulled through /api/pull"""

    def __init__(self, port, models=()):
        self.port = port
        self.models = list(models)
        self.pulled = []
        self._httpd = None

    def start(self):
        ollama = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # pylint: disable=invalid-name
                body = {"models": [{"name": name} for name in ollama.models]} if self.path == "/api/tags" else {}
                self._send([json.dumps(body)])

            def do_POST(self):  # pylint: disable=invalid-name
                model = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["model"]
                if model == "unknown":
                    self._send([json.dumps({"error": "pull model manifest: file does not exist"})])
                    return
                ollama.pulled.append(model)
                ollama.models.append(f"{model}:latest")
                self._send([json.dumps(line) for line in ({"status": "pulling manifest"},
                                                          {"status": "pulling", "total": 10, "completed": 5},
                                                          {"status": "success"})])

            def _send(self, lines):
                payload = "".join(line + "\n" for line in lines).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


class FakeContainer:
    """A container whose start runs a FakeOllama on the published port. `crash` makes it exit at once."""

    def __init__(self, name, ollama, status="created", crash=False, **options):
        self.name = name
        self.ollama = ollama
        self.status = status
        self.crash = crash
        self.options = options
        self.calls = []

    def reload(self):
        pass

    def start(self):
        self.calls.append("start")
        if self.crash:
            self.status = "exited"
            return
        self.status = "running"
        self.ollama.start()

    def stop(self, timeout):
        self.calls.append("stop")
        self.status = "exited"
        self.ollama.stop()

    def logs(self, tail):
        return b"Error: no compatible GPUs were discovered"


class FakeEngine:
    """A Docker engine with at most one container, and the images it has.

    :ivar created: the options the container was created with, if it was
    :ivar pulled: the images pulled
    """

    def __init__(self, ollama, container=None, images=()):
        self.ollama = ollama
        self.container = container
        self.images_present = set(images)
        self.created = None
        self.pulled = []
        self.containers = SimpleNamespace(get=self._get, create=self._create)
        self.images = SimpleNamespace(get=self._image, pull=self._pull)

    def _get(self, name):
        if self.container is None or self.container.name != name:
            raise docker.errors.NotFound(f"No such container: {name}")
        return self.container

    def _create(self, image, name, **options):
        self.created = {"image": image, **options}
        self.container = FakeContainer(name, self.ollama)
        return self.container

    def _image(self, image):
        if image not in self.images_present:
            raise docker.errors.ImageNotFound(f"No such image: {image}")

    def _pull(self, image):
        self.pulled.append(image)
        self.images_present.add(image)
