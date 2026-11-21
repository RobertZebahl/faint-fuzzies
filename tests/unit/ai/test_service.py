"""The app's AI service: the model server for the app's lifetime, the index kept up to date, and Questions and
searches through it - with a fake server and the fake client of tests/unit/ai/fakes.py."""
import shutil
from contextlib import contextmanager
from datetime import date

import pytest

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.question import Context
from faint_fuzzies.ai.service import AiService, AiState
from faint_fuzzies.config import AiConfig
from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES

CONFIG = AiConfig("http://fake/v1", "chat", "model")


class FakeServer:
    """Counts the servers started and stopped; `fails` makes the next start fail."""

    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.fails = False

    @contextmanager
    def __call__(self, config, log_dir, on_progress=None, models=()):
        if self.fails:
            raise AiError("cannot start the model server")
        self.started += 1
        try:
            yield
        finally:
            self.stopped += 1


@pytest.fixture
def data(tmp_path):
    data_dir = shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")
    return data_dir, load_data_dir(data_dir, load_static_catalogues(data_dir))


def service_for(data_dir, server=None, client=None):
    return AiService(CONFIG, data_dir, server or FakeServer(), client or FakeClient())


def test_the_server_is_started_once_and_stopped_with_the_app(data):
    data_dir, loaded = data
    server = FakeServer()
    service = service_for(data_dir, server)
    service.start(loaded.collection.objects).join()
    assert (service.state, service.answers) == (AiState.READY, True)
    service.refresh(loaded.collection.objects).join()
    assert server.started == 1
    service.stop()
    assert server.stopped == 1 and not service.answers


def test_a_failed_start_is_tried_again_on_the_next_reload(data):
    data_dir, loaded = data
    server = FakeServer()
    server.fails = True
    service = service_for(data_dir, server)
    service.start(loaded.collection.objects).join()
    assert (service.state, service.message) == (AiState.FAILED, "cannot start the model server")
    with pytest.raises(AiError, match="cannot start"):
        service.ask("Galaxien", Context(loaded.collection, loaded.observers, date(2026, 11, 21)))
    server.fails = False
    service.refresh(loaded.collection.objects).join()
    assert service.state is AiState.READY


def test_a_search_ranks_the_matches_by_their_descriptions(data):
    data_dir, loaded = data
    service = service_for(data_dir)
    service.start(loaded.collection.objects).join()
    matches = filter_objects(loaded.collection, FilterSpec.from_dict({}), loaded.references, loaded.observers,
                             loaded.findings)
    steps = []
    results = service.search(matches, "Kugelhaufen", lambda step, fraction: steps.append(step))
    assert results[0].match.object.names[0] == "Messier 13"
    assert {result.verdict for result in results} <= {"yes", "partly"}
    assert any("judging" in step for step in steps)


def test_a_search_before_the_index_is_there_says_so(data):
    data_dir, _loaded = data
    service = service_for(data_dir)
    service._up = True  # pylint: disable=protected-access  # the server answers, the index is not built yet
    with pytest.raises(AiError, match="still being built"):
        service.search([], "Kugelhaufen")


def test_a_question_is_asked_through_the_server(data):
    data_dir, loaded = data
    client = FakeClient()
    client.answer = {"filter": {"type": ["GC"]}, "text": "aufgelöst", "ignored": []}
    service = service_for(data_dir, client=client)
    service.start(loaded.collection.objects).join()
    answer = service.ask("Kugelsternhaufen, die aufgelöst waren",
                         Context(loaded.collection, loaded.observers, date(2026, 11, 21)))
    assert (answer.filter, answer.text) == ({"type": ["GC"]}, "aufgelöst")
