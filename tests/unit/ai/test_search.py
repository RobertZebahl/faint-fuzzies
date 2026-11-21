"""Description search: ranking a filter's matches by their Descriptions, with the keyword embeddings of
tests/unit/ai/fakes.py over a copy of tests/fixtures/datadir."""
import shutil

import pytest

from faint_fuzzies.ai.index import update_index
from faint_fuzzies.ai.search import query_vector, rank
from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES, load_world


@pytest.fixture
def searched(tmp_path):
    data_dir = shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")
    world = load_world(data_dir)
    client = FakeClient()
    index = update_index(data_dir, world.collection.objects, client, "model")

    def search(text, spec=None, min_score=0.5, limit=30):
        matches = filter_objects(world.collection, FilterSpec.from_dict(spec or {}), world.references)
        return rank(matches, query_vector(client, "model", text), index, min_score, limit)
    return search


def test_the_object_whose_description_fits_best_comes_first(searched):
    results = searched("Kugelhaufen")
    assert results[0].match.object.label == "Messier 13"
    assert results[0].score == pytest.approx(max(score for _found, score in results[0].hits))


def test_only_the_observations_above_the_minimum_score_are_hits(searched):
    hits = searched("Kugelhaufen")[0].hits
    assert [found.observation.descriptions[0][1] for found, _score in hits] == ["Kugelhaufen",
                                                                               "Kugelhaufen mit Filter"]


def test_an_object_without_any_hit_is_left_out(searched):
    labels = [result.match.object.label for result in searched("Kugelhaufen")]
    assert "STF999" not in labels


def test_the_limit_counts_objects_and_each_keeps_all_its_hits(searched):
    everything = searched("Text", min_score=0.0)
    results = searched("Text", min_score=0.0, limit=2)
    assert results == everything[:2]
    assert any(len(result.hits) > 1 for result in results)


def test_the_hits_of_an_object_are_sorted_best_first(searched):
    for result in searched("Text", min_score=0.0):
        scores = [score for _found, score in result.hits]
        assert scores == sorted(scores, reverse=True)


def test_the_filter_decides_which_objects_are_searched(searched):
    assert searched("Doppelstern", spec={"name": "IC348"}) == []
    assert searched("Doppelstern") != []


def test_results_are_sorted_by_their_best_score(searched):
    scores = [result.score for result in searched("Text", min_score=0.0)]
    assert scores == sorted(scores, reverse=True)
