"""The HTTP client against a tiny real server in a thread that answers like the embeddings endpoint of an
OpenAI-compatible API (or with whatever error a test sets)."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from faint_fuzzies.ai import AiAnswerError, AiError
from faint_fuzzies.ai.client import AiClient


@pytest.fixture
def server():
    state = {"status": 200, "body": None, "requests": [], "chat": "{}"}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # pylint: disable=invalid-name
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, request))
            refuse = state.get("refuse_reasoning") and "reasoning_effort" in request
            if state.get("slow"):
                threading.Event().wait(state["slow"])
            if refuse:
                body = '{"error": "unsupported parameter: reasoning_effort"}'
            elif self.path.endswith("/chat/completions") and state["body"] is None:
                body = {"choices": [{"message": {"content": state["chat"]}}]}
            else:
                body = state["body"] or {"data": [{"index": i, "embedding": [float(len(text)), 1.0]}
                                                  for i, text in reversed(list(enumerate(request["input"])))]}
            payload = (body if isinstance(body, str) else json.dumps(body)).encode()
            self.send_response(400 if refuse else state["status"])
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


def test_a_chat_answer_is_parsed_and_its_thinking_dropped(server):
    server["chat"] = '<think>\nThe user wants a verdict.\n</think>\n{"verdicts": []}'
    answer = AiClient(server["url"], 5).chat_json("qwen3:8b", [{"role": "user", "content": "x"}], {"type": "object"})
    assert answer == {"verdicts": []}
    path, request = server["requests"][0]
    assert path == "/v1/chat/completions"
    assert request["temperature"] == 0
    assert request["response_format"]["json_schema"]["schema"] == {"type": "object"}


def test_a_chat_answer_that_is_not_json_is_an_error(server):
    server["chat"] = "Sure! Here are the verdicts."
    with pytest.raises(AiError, match="did not answer with JSON"):
        AiClient(server["url"], 5).chat_json("chat", [{"role": "user", "content": "x"}], {})


def test_a_chat_asks_the_model_not_to_think(server):
    AiClient(server["url"], 5).chat_json("qwen3:8b", [{"role": "user", "content": "x"}], {})
    assert server["requests"][0][1]["reasoning_effort"] == "none"


def test_a_server_that_refuses_the_reasoning_field_is_asked_again_without_it_and_never_with_it_again(server):
    server["refuse_reasoning"] = True
    client = AiClient(server["url"], 5)
    assert client.chat_json("chat", [{"role": "user", "content": "x"}], {}) == {}
    client.chat_json("chat", [{"role": "user", "content": "y"}], {})
    assert ["reasoning_effort" in request for _path, request in server["requests"]] == [True, False, False]


def test_another_error_of_a_chat_is_not_retried(server):
    server["status"], server["body"] = 404, 'model "chat" not found'
    with pytest.raises(AiError, match="404"):
        AiClient(server["url"], 5).chat_json("chat", [{"role": "user", "content": "x"}], {})
    assert len(server["requests"]) == 1


def test_the_token_limit_is_sent_only_when_given(server):
    client = AiClient(server["url"], 5)
    client.chat_json("chat", [{"role": "user", "content": "x"}], {}, max_tokens=800)
    client.chat_json("chat", [{"role": "user", "content": "x"}], {})
    assert [request.get("max_tokens") for _path, request in server["requests"]] == [800, None]


def test_an_answer_cut_off_is_an_answer_error_with_its_length_and_start(server):
    server["chat"] = '{"filter":' + "\n" * 300 + '"'
    with pytest.raises(AiAnswerError, match=r"did not answer with JSON \(311 characters.*'\{\"filter\":\\n"):
        AiClient(server["url"], 5).chat_json("chat", [{"role": "user", "content": "x"}], {})


def test_a_server_that_takes_too_long_is_said_to_give_no_answer(server):
    server["slow"] = 1.5
    with pytest.raises(AiError, match=r"gave no answer within 0.5 s"):
        AiClient(server["url"], 0.5).chat_json("chat", [{"role": "user", "content": "x"}], {})
