"""Measuring the reranking and the Questions against test sets, with the chat model of tests/unit/ai/fakes.py;
the cases are written to a temporary file."""
import json
from datetime import date
from types import SimpleNamespace

import pytest

from faint_fuzzies.ai.evaluation import evaluate, evaluate_questions, read_cases, read_questions
from faint_fuzzies.ai.question import Context
from faint_fuzzies.domain.findings import CatalogueError
from faint_fuzzies.domain.names import set_object_name_abbreviations
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import fake_collection


@pytest.fixture(autouse=True)
def no_abbreviations():
    """Abbreviations are global; other tests leave a data directory's behind."""
    set_object_name_abbreviations([])
    yield
    set_object_name_abbreviations([])


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


QUESTION_COLLECTION = fake_collection(["own.json"], [SimpleNamespace(names=("Messier 31", "M31"), groups=())])


def question(text, expected_filter, expected_text=None):
    return {"question": text, "filter": expected_filter, "text": expected_text}


def asked_with(answers, cases):
    """The report on `cases`, the fake model answering the n-th question with answers[n]."""
    client = FakeClient()
    replies = iter(answers)
    original = client.chat_json
    client.chat_json = lambda model, messages, schema, max_tokens=None: next(replies) if "filter" in schema["properties"] \
        else original(model, messages, schema)
    return evaluate_questions(client, "chat", cases, Context(QUESTION_COLLECTION, None, date(2026, 11, 21)))


def test_a_question_agrees_when_its_filter_is_the_same_whatever_the_order_and_form():
    report = asked_with([{"filter": {"type": ["**", "Gx"], "aperture": [None, 102.0], "name_group": ["m 31"]},
                          "text": "Details", "ignored": []}],
                        [question("q", {"type": ["Gx", "**"], "aperture": [None, 102], "name_group": "M31"},
                                  "Details gesehen")])
    assert (report["cases"], report["agree"], report["mismatches"]) == (1, 1, [])


def test_a_range_is_not_the_same_the_other_way_round():
    report = asked_with([{"filter": {"aperture": [102, None]}, "text": None, "ignored": []}],
                        [question("q", {"aperture": [None, 102]})])
    assert report["filters_agree"] == 0 and report["texts_agree"] == 1
    assert report["mismatches"][0]["got"]["filter"] == {"aperture": [102, None]}


def test_a_text_only_has_to_be_there_or_not():
    report = asked_with([{"filter": {}, "text": "Spiralarme", "ignored": []},
                         {"filter": {}, "text": None, "ignored": []}],
                        [question("a", {}, "Details gesehen"), question("b", {}, "Farben")])
    assert (report["agree"], report["texts_agree"]) == (1, 1)
    assert report["mismatches"][0]["question"] == "b"


def test_a_rejected_answer_is_a_mismatch_with_its_error():
    report = asked_with([{"filter": {"type": ["Galaxy"]}, "text": None, "ignored": []}],
                        [question("q", {"type": ["Gx"]})])
    assert report["agree"] == 0 and "not valid" in report["mismatches"][0]["error"]


@pytest.mark.parametrize("content, message", [
    pytest.param([{"question": "q", "text": None}], "needs a question, a filter and a text", id="no filter"),
    pytest.param([{"question": "q", "filter": {}}], "needs a question, a filter and a text", id="no text"),
])
def test_an_unusable_question_set_is_an_error(tmp_path, content, message):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(CatalogueError, match=message):
        read_questions(path)
