"""The HTTP client of the model server's OpenAI-compatible API (Ollama, llama.cpp's llama-server, LM Studio)."""
import json
import urllib.error
import urllib.request
from typing import Any

from faint_fuzzies.ai import AiError


class AiClient:
    """Sends requests to one model server.

    :ivar url: the base URL of the API, for example "http://localhost:11434/v1"
    :ivar timeout: seconds to wait for one answer
    """

    def __init__(self, url: str, timeout: float):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """The embedding vector of each text, in the order of `texts`.

        :param model: the embedding model's name, as the server knows it
        :param texts: the texts to embed
        :returns: one vector per text
        :raises AiError: when the server cannot be reached or answers with something else than one vector
            per text
        """
        if not texts:
            return []
        answer = self._post("/embeddings", {"model": model, "input": texts})
        try:
            data = sorted(answer["data"], key=lambda item: item["index"])
            vectors = [[float(value) for value in item["embedding"]] for item in data]
        except (KeyError, TypeError, ValueError) as exc:
            raise AiError(f"the model server's embeddings answer is not understood: {exc!r}") from exc
        if len(vectors) != len(texts):
            raise AiError(f"the model server returned {len(vectors)} embeddings for {len(texts)} texts")
        return vectors

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        request = urllib.request.Request(self.url + path, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace").strip()[:500]
            raise AiError(f"the model server at {self.url} answered {exc.code}: {detail or exc.reason}") from exc
        except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
            reason = getattr(exc, "reason", exc)
            raise AiError(f"cannot reach the model server at {self.url}: {reason}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise AiError(f"the model server at {self.url} did not answer with JSON") from exc
