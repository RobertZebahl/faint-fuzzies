"""Measuring the reranking against a test set, with the chat model of tests/unit/ai/fakes.py; the cases are
written to a temporary file."""
import json

import pytest

from faint_fuzzies.ai.evaluation import evaluate, read_cases
from faint_fuzzies.domain.findings import CatalogueError
from tests.unit.ai.fakes import FakeClient


def case(note, expected, search="Staubband"):
    return {"search": search, "note": note, "expected": expected}


def test_the_report_counts_agreements_and_lists_the_mismatches():
    cases = [case("Staubband deutlich.", "yes"), case("Kein Staubband.", "no"),
             case("Ansätze vom Staubband.", "yes"), case("Ovale Form.", "partly")]
    report = evaluate(FakeClient(), "chat", cases)
    assert (report["cases"], report["agree"], report["accuracy"]) == (4, 2, 0.5)
    assert [(m["note"], m["got"]) for m in report["mismatches"]] == [("Ansätze vom Staubband.", "partly"),
                                                                       ("Ovale Form.", "no")]
    assert report["confusion"]["yes"] == {"yes": 1, "partly": 1, "no": 0, "none": 0}


def test_cases_are_judged_per_search_in_batches():
    client = FakeClient()
    cases = [case(f"Staubband {n}.", "yes") for n in range(12)] + [case("Spiralarme.", "yes", search="Spiralarme")]
    assert evaluate(client, "chat", cases)["agree"] == 13
    assert [chat.split("\n", 1)[0] for chat in client.chats] == ["Search: Staubband", "Search: Staubband",
                                                                   "Search: Spiralarme"]


def test_a_note_the_model_leaves_out_counts_as_none():
    report = evaluate(FakeClient(skip={"Staubband."}), "chat", [case("Staubband.", "yes")])
    assert report["confusion"]["yes"]["none"] == 1 and report["mismatches"][0]["got"] is None


def test_the_cases_are_read_from_the_file(tmp_path):
    path = tmp_path / "rerank.json"
    path.write_text(json.dumps([case("Staubband.", "yes") | {"object": "NGC891"}]), encoding="utf-8")
    assert read_cases(path)[0]["object"] == "NGC891"


@pytest.mark.parametrize("content, message", [
    pytest.param(None, "no test set", id="missing file"),
    pytest.param([{"search": "x", "note": "y", "expected": "maybe"}], "case 1 needs", id="bad verdict"),
    pytest.param([{"note": "y", "expected": "yes"}], "case 1 needs", id="no search"),
])
def test_an_unusable_test_set_is_an_error(tmp_path, content, message):
    path = tmp_path / "rerank.json"
    if content is not None:
        path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(CatalogueError, match=message):
        read_cases(path)
