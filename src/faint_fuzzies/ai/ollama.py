"""What only Ollama has beyond the OpenAI-compatible API: downloading a model the server does not have yet. Used
only with [ai.docker], where the server is known to be Ollama."""
import json
import urllib.error
import urllib.request
from collections.abc import Callable

from faint_fuzzies.ai import AiError


def api_root(url: str) -> str:
    """Ollama's own API root for the OpenAI-compatible base URL ("http://localhost:11434/v1" -> its host)."""
    return url.rstrip("/").removesuffix("/v1")


def has_model(root: str, model: str, timeout: float) -> bool:
    """Whether the server has the model; a name without a tag means its "latest" tag, as Ollama reads it."""
    answer = _request(root + "/api/tags", None, timeout)
    try:
        names = {item["name"] for item in json.loads(answer.read())["models"]}
    except (KeyError, TypeError, ValueError) as exc:
        raise AiError(f"the model server's list of models is not understood: {exc!r}") from exc
    finally:
        answer.close()
    return model in names or (":" not in model and f"{model}:latest" in names)


def pull_model(root: str, model: str, timeout: float, on_progress: Callable[[str, float], None] | None) -> None:
    """Downloads the model into the server, telling `on_progress` how far it got.

    :raises AiError: when the server cannot download it (an unknown name, no network)
    """
    with _request(root + "/api/pull", {"model": model, "stream": True}, timeout) as answer:
        for line in answer:
            try:
                status = json.loads(line)
            except ValueError:
                continue
            if "error" in status:
                raise AiError(f"the model server cannot download {model}: {status['error']}")
            if on_progress and status.get("total"):
                on_progress(f"downloading the model {model}", status.get("completed", 0) / status["total"])


def ensure_model(url: str, model: str, timeout: float, on_progress: Callable[[str, float], None] | None) -> None:
    root = api_root(url)
    if not has_model(root, model, timeout):
        pull_model(root, model, timeout, on_progress)


def _request(url: str, payload: dict | None, timeout: float):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                     method="GET" if payload is None else "POST")
    try:
        return urllib.request.urlopen(request, timeout=timeout)  # pylint: disable=consider-using-with
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()[:500]
        raise AiError(f"the model server answered {exc.code} at {url}: {detail or exc.reason}") from exc
    except (TimeoutError, urllib.error.URLError, ConnectionError) as exc:
        raise AiError(f"cannot reach the model server at {url}: {getattr(exc, 'reason', exc)}") from exc
