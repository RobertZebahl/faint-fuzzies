"""The model server for the app's lifetime: started in the background when the app starts (without holding up the
data load), the description index brought up to date after it and after every Reload, and stopped with the app -
only when the app started it (see ai.server). The Browse page asks its Questions and runs its Description
searches through it, from a worker thread; what it is doing is kept in `state` and `progress`, for the page to
show."""
import threading
from collections.abc import Callable, Iterable, Sequence
from contextlib import AbstractContextManager, ExitStack
from enum import Enum
from pathlib import Path
from typing import Any

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.index import CACHE_DIR, DescriptionIndex, update_index
from faint_fuzzies.ai.question import Answer, Context, ask
from faint_fuzzies.ai.search import SearchResult, query_vector, rank
from faint_fuzzies.config import AiConfig
from faint_fuzzies.domain.filters import Match
from faint_fuzzies.domain.model import Object

Progress = Callable[[str, float], None]
ServerFactory = Callable[..., AbstractContextManager[Any]]


class AiState(Enum):
    """What the service can do: STARTING until the server answers, INDEXING while the index is brought up to
    date (a Question works already, a search over the index of the last time), READY, or FAILED with a
    message."""
    STARTING = "starting"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


def _running_server(config: AiConfig, log_dir: Path, on_progress: Progress | None = None,
                    models: tuple[str, ...] = ()) -> AbstractContextManager[Any]:
    from faint_fuzzies.ai.server import running_server
    return running_server(config, log_dir, on_progress, models=models)


class AiService:  # pylint: disable=too-many-instance-attributes  # what it shows, and what it holds
    """The model server, its client and the description index of the loaded data, for as long as the app runs.

    :param config: the AI settings
    :param data_dir: the data directory, where the index is cached
    :param server: starts the server for the time of a `with` block (ai.server.running_server; a test's own)
    :param client: the client to reach it with; one for config.url when not given
    """

    def __init__(self, config: AiConfig, data_dir: Path, server: ServerFactory = _running_server,
                 client: Any = None):
        self.config = config
        self.data_dir = data_dir
        self.state = AiState.STARTING
        self.message = ""
        self.progress: tuple[str, float] = ("Starting the model server…", 0.0)
        self._server = server
        self._client = client if client is not None else AiClient(config.url, config.timeout)
        self._stack = ExitStack()
        self._index: DescriptionIndex | None = None
        self._up = False  # the server answers (and, when started here, is stopped by stop)
        self._lock = threading.Lock()  # one start or index update at a time
        self._wanted = 0  # counts index updates asked for: only the newest one's outcome counts

    def start(self, objects: Iterable[Object]) -> threading.Thread:
        """Starts the server and then indexes `objects`, in the background.

        :returns: the thread doing it, for a test to wait for
        """
        return self._background(self._start, list(objects))

    def refresh(self, objects: Iterable[Object]) -> threading.Thread:
        """Brings the index up to date with `objects` (after a Reload), in the background; tries to start the
        server again first when that had failed."""
        return self._background(self._start, list(objects))

    def stop(self) -> None:
        """Stops the server, when it was started here."""
        self._stack.close()
        self._up = False

    @property
    def answers(self) -> bool:
        """Whether a Question can be asked: the server answers."""
        return self._up

    def ask(self, question: str, context: Context) -> Answer:
        """The answer to `question` (see ai.question.ask).

        :raises AiError: when the server fails or the answer cannot be used
        """
        self._check()
        return ask(self._client, self.config.chat_model, question, context, self._report)

    def search(self, matches: Sequence[Match], text: str, on_progress: Progress | None = None) -> list[SearchResult]:
        """The matches whose Descriptions fit `text`, reranked by the chat model, best first and at most
        config.limit of them (as `filter --search`).

        :param on_progress: told (step, fraction done) as the search goes on; `progress` always is
        :raises AiError: when the server fails, or there is no index yet
        """
        from faint_fuzzies.ai import rerank

        def report(step: str, fraction: float) -> None:
            self._report(step, fraction)
            if on_progress:
                on_progress(step, fraction)
        self._check()
        index = self._index
        if index is None:
            step, fraction = self.progress
            raise AiError(f"the description index is still being built ({step} {fraction:.0%})")
        report(f"embedding the search text with {self.config.embedding_model}", 0.0)
        query = query_vector(self._client, self.config.embedding_model, text)
        ranked = rank(matches, query, index, rerank.MIN_SCORE, len(matches))
        return rerank.rerank(self._client, self.config, text, ranked, report).results

    def _check(self) -> None:
        if not self._up:
            raise AiError(self.message if self.state is AiState.FAILED else "the model server is still starting")

    def _background(self, target: Callable[[list[Object], int], None], objects: list[Object]) -> threading.Thread:
        self._wanted += 1
        thread = threading.Thread(target=target, args=(objects, self._wanted), daemon=True, name="ai-service")
        thread.start()
        return thread

    def _report(self, step: str, fraction: float) -> None:
        self.progress = (step[:1].upper() + step[1:], fraction)

    def _start(self, objects: list[Object], wanted: int) -> None:
        with self._lock:
            if not self._up:
                self.state, self.message = AiState.STARTING, ""
                self.progress = ("Starting the model server…", 0.0)
                try:
                    self._stack.enter_context(self._server(
                        self.config, self.data_dir / CACHE_DIR, self._report,
                        models=(self.config.embedding_model, self.config.chat_model)))
                except AiError as exc:
                    self.state, self.message = AiState.FAILED, str(exc)
                    return
                self._up = True
        self._update(objects, wanted)

    def _update(self, objects: list[Object], wanted: int) -> None:
        with self._lock:
            if wanted != self._wanted:  # a newer Reload's update follows
                return
            self.state = AiState.INDEXING
            self.progress = ("Indexing the descriptions…", 0.0)
            try:
                index = update_index(self.data_dir, objects, self._client, self.config.embedding_model,
                                     self._report)
            except AiError as exc:  # the server still answers: a Question works, a search needs the index
                self.state, self.message = AiState.FAILED, f"the description index could not be updated: {exc}"
                return
            if wanted == self._wanted:
                self._index = index
                self.state = AiState.READY
