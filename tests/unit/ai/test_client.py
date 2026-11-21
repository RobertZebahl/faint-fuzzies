"""The HTTP client against a tiny real server in a thread that answers like the embeddings endpoint of an
OpenAI-compatible API (or with whatever error a test sets)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient


@pytest.fixture
def server():
    state = {"status": 200, "body": None, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # pylint: disable=invalid-name
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, request))
            body = state["body"] or {"data": [{"index": i, "embedding": [float(len(text)), 1.0]}
                                              for i, text in reversed(list(enumerate(request["input"])))]}
            payload = (body if isinstance(body, str) else json.dumps(body)).encode()
            self.send_response(state["status"])
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}/v1/"
    yield state
    httpd.shutdown()


def test_the_vectors_come_back_in_the_order_of_the_texts(server):
    vectors = AiClient(server["url"], 5).embed("bge-m3", ["a", "bbb"])
    assert vectors == [[1.0, 1.0], [3.0, 1.0]]
    assert server["requests"] == [("/v1/embeddings", {"model": "bge-m3", "input": ["a", "bbb"]})]


def test_no_texts_need_no_request(server):
    assert AiClient(server["url"], 5).embed("bge-m3", []) == []
    assert server["requests"] == []


def test_an_error_status_names_the_servers_message(server):
    server["status"], server["body"] = 404, 'model "bge-m3" not found'
    with pytest.raises(AiError, match='answered 404: model "bge-m3" not found'):
        AiClient(server["url"], 5).embed("bge-m3", ["a"])


@pytest.mark.parametrize("body, message", [
    pytest.param("<html>", "did not answer with JSON", id="not JSON"),
    pytest.param({"data": [{"index": 0}]}, "not understood", id="no embedding"),
    pytest.param({"data": []}, "0 embeddings for 1 texts", id="too few"),
])
def test_an_answer_that_cannot_be_used_is_an_error(server, body, message):
    server["body"] = body
    with pytest.raises(AiError, match=message):
        AiClient(server["url"], 5).embed("bge-m3", ["a"])


def test_a_server_that_is_not_there_is_an_error():
    with pytest.raises(AiError, match="cannot reach the model server"):
        AiClient("http://127.0.0.1:9/v1", 2).embed("bge-m3", ["a"])
