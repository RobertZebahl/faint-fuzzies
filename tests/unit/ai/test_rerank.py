"""Reranking a Description search with the chat model of tests/unit/ai/fakes.py, over hand-made hits: each
Object (a stand-in with a label) has one observation per text, and a hit's score is given directly."""
import re
from types import SimpleNamespace

import pytest

from faint_fuzzies.ai import rerank as rerank_module
from faint_fuzzies.ai.rerank import rerank as rerank_with_rubric
from faint_fuzzies.ai.search import Hit, SearchResult
from faint_fuzzies.config import AiConfig
from faint_fuzzies.domain.filters import Match
from faint_fuzzies.domain.observation import FoundObservation, Observation
from faint_fuzzies.domain.seen import SeenStatus
from tests.unit.ai.fakes import FakeClient


def rerank(*args):
    """The reranked results alone."""
    return rerank_with_rubric(*args).results


def config(limit=30):
    return AiConfig("http://fake/v1", "chat", "embed", limit=limit)


def result(label, *texts_and_scores):
    """A SearchResult of an Object `label` whose observations have these (text, score) hits, best first."""
    obj = SimpleNamespace(label=label)
    found = [FoundObservation(Observation({"DESCRIPTION": text}, False, None, ()), obj)
             for text, _score in texts_and_scores]
    hits = tuple(Hit(f, score) for f, (_text, score) in zip(found, texts_and_scores))
    return SearchResult(Match(obj, tuple(found), SeenStatus.SEEN), hits)


def labels(results):
    return [r.match.object.label for r in results]


def texts(r):
    return [hit.found.observation.descriptions[0][1] for hit in r.hits]


def test_a_negated_hit_is_dropped_even_when_it_scores_best():
    results = rerank(FakeClient(), config(), "Staubband sichtbar", [
        result("NGC891", ("Das Staubband war nicht sichtbar.", 0.70)),
        result("M31", ("Staubband deutlich.", 0.66)),
    ])
    assert labels(results) == ["M31"]


def test_yes_comes_before_partly_whatever_the_scores():
    results = rerank(FakeClient(), config(), "Struktur gesehen", [
        result("M106", ("Möglicherweise Ansätze von Struktur.", 0.75)),
        result("M81", ("Struktur gut zu sehen.", 0.65)),
    ])
    assert labels(results) == ["M81", "M106"]
    assert [r.verdict for r in results] == ["yes", "partly"]


def test_an_object_keeps_only_its_hits_judged_yes_or_partly_the_yes_first():
    [only] = rerank(FakeClient(), config(), "Spiralarme", [
        result("M51", ("Ansätze von Spiralarme, möglicherweise.", 0.74), ("Keine Spiralarme.", 0.72),
               ("Spiralarme deutlich.", 0.69)),
    ])
    assert texts(only) == ["Spiralarme deutlich.", "Ansätze von Spiralarme, möglicherweise."]
    assert only.score == 0.69


def test_a_hit_the_model_leaves_out_is_dropped():
    client = FakeClient(skip={"Staubband zwei."})
    [only] = rerank(client, config(), "Staubband", [result("M31", ("Staubband eins.", 0.7), ("Staubband zwei.", 0.6))])
    assert texts(only) == ["Staubband eins."]


def test_only_the_best_candidates_are_judged_in_batches(monkeypatch):
    monkeypatch.setattr(rerank_module, "CANDIDATES", 25)
    client = FakeClient()
    many = [result(f"G{n}", (f"Staubband {n}.", 0.9 - n / 100)) for n in range(30)]
    results = rerank(client, config(100), "Staubband", many)
    assert labels(results) == [f"G{n}" for n in range(25)]
    assert [len(re.findall(r"^\d+\. ", chat, re.MULTILINE)) for chat in client.chats] == [10, 10, 5]


def test_the_limit_counts_objects_after_reranking():
    many = [result(f"G{n}", (f"Staubband {n}.", 0.9 - n / 100)) for n in range(5)]
    assert labels(rerank(FakeClient(), config(2), "Staubband", many)) == ["G0", "G1"]


def test_a_long_note_is_cut_short_and_the_languages_are_joined():
    found = FoundObservation(Observation({"DESCRIPTION_DE": "Staub " * 200, "DESCRIPTION_EN": "Dust"}, False, None,
                                         ()), SimpleNamespace(label="x"))
    note = rerank_module._note(Hit(found, 0.7))  # pylint: disable=protected-access
    assert note.endswith("…") and len(note) == rerank_module.TEXT_LENGTH + 1
    assert "/" not in note  # the German text alone already fills the note


@pytest.mark.parametrize("answer", [
    pytest.param({"verdicts": []}, id="too few letters"),
    pytest.param({"verdicts": ["maybe"]}, id="unknown letter"),
    pytest.param({"verdicts": [1]}, id="not a letter"),
    pytest.param({"verdicts": "y"}, id="not a list"),
    pytest.param([], id="not an object"),
])
def test_an_unusable_verdict_leaves_the_hit_unjudged(answer):
    client = FakeClient()
    client.chat_json = lambda model, messages, schema: {"yes": "", "partly": "", "no": ""} if "yes" in str(
        schema) else answer
    assert rerank(client, config(), "Staubband", [result("M31", ("Staubband.", 0.7))]) == []


def test_the_answer_must_have_exactly_one_letter_per_note():
    seen = []
    client = FakeClient()
    client.chat_json = lambda model, messages, schema: seen.append(schema) or {"verdicts": ["y", "n", "y"]}
    assert rerank_module.judge_notes(client, "chat", "Staubband", ["a", "b"], {}) == ["yes", "no"]
    assert seen[0]["properties"]["verdicts"] | {"items": None} == {"type": "array", "items": None,
                                                                   "minItems": 2, "maxItems": 2}


def test_the_rubric_is_written_once_per_search_and_shown_to_every_batch(monkeypatch):
    monkeypatch.setattr(rerank_module, "CANDIDATES", 25)
    client = FakeClient()
    many = [result(f"G{n}", (f"Staubband {n}.", 0.9 - n / 100)) for n in range(30)]
    outcome = rerank_with_rubric(client, config(), "Staubband", many)
    assert client.rubrics == ["Search: Staubband"]
    assert outcome.rubric == {"yes": "it was seen.", "partly": "only traces.", "no": "anything else."}
    assert all("Rubric:\ny: it was seen.\np: only traces.\nn: anything else.\n" in chat for chat in client.chats)


def test_a_rubric_answer_without_some_verdict_leaves_it_empty():
    client = FakeClient()
    client.chat_json = lambda model, messages, schema: {"yes": "  named\n colours "}
    assert rerank_module.write_rubric(client, "chat", "Farben") == {"yes": "named colours", "partly": "", "no": ""}
