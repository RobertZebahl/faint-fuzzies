"""Questions (faint_fuzzies.ai.question) with the chat model of tests/unit/ai/fakes.py, which gives the answer a
test sets, over stand-in Objects that only have names and groups."""
from datetime import date
from types import SimpleNamespace

import pytest

from faint_fuzzies.ai import AiAnswerError, AiError
from faint_fuzzies.ai.question import Answer, Context, QuestionError, answer_of, ask, resolve_names, schema
from faint_fuzzies.domain.names import set_object_name_abbreviations
from faint_fuzzies.domain.observer import Observer, Observers, Scope
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import fake_collection


def obj(*names, groups=()):
    return SimpleNamespace(names=names, groups=groups)


COLLECTION = fake_collection(["own.json", "wds.json"], [
    obj("Messier 31", "M31", "NGC224"), obj("NGC891"), obj("Albireo", groups=("STFA43",)), obj("M 13", "M13")])
OBSERVERS = Observers("observers.json", [Observer(id="anna", firstname="Anna", surname="Example", scope=Scope.GLOBAL),
                                         Observer(id="me", firstname="Me", surname="Myself", scope=Scope.OWNER)], [])


@pytest.fixture(autouse=True)
def no_abbreviations():
    """Abbreviations are global; other tests leave a data directory's behind."""
    set_object_name_abbreviations([])
    yield
    set_object_name_abbreviations([])


def asked(answer, question="Welche Galaxien zeigten Details mit bis zu 4 Zoll?"):
    client = FakeClient()
    client.answer = answer
    return client, ask(client, "chat", question, Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))


def test_the_answer_gives_the_filter_and_the_search_text():
    _client, answer = asked({"filter": {"type": ["Gx"], "aperture": [None, 102]}, "text": "Details  gesehen",
                             "ignored": []})
    assert answer == Answer({"type": ["Gx"], "aperture": [None, 102]}, "Details gesehen", ())


def test_criteria_that_ask_for_nothing_are_dropped():
    _client, answer = asked({"filter": {"type": ["Gx"], "constellation": [], "magnitude": [None, None],
                                        "observer": None}, "text": " ", "ignored": ["", "im Winter"]})
    assert answer == Answer({"type": ["Gx"]}, None, ("im Winter",))


@pytest.mark.parametrize("written, real", [
    pytest.param("M 31", ["M31"], id="with a space"),
    pytest.param("m31", ["M31"], id="other case"),
    pytest.param("Messier 31", ["Messier 31"], id="long form"),
    pytest.param("NGC 891", ["NGC891"], id="catalogue number with a space"),
    pytest.param("M13", ["M 13", "M13"], id="every spelling the data has"),
    pytest.param("stfa43", ["STFA43"], id="a group name"),
])
def test_names_are_found_as_the_data_spells_them(written, real):
    assert resolve_names([written], COLLECTION) == real


def test_a_name_is_found_by_its_abbreviation_too():
    set_object_name_abbreviations([("Messier (.*)", ["M{}"])])
    assert resolve_names(["Messier 13"], COLLECTION) == ["M 13", "M13"]


def test_an_unknown_name_is_an_error_with_the_closest_names():
    with pytest.raises(AiError, match=r"no object is named 'Albiero'; did you mean Albireo\?"):
        resolve_names(["Albiero"], COLLECTION)


def test_the_answers_names_are_replaced_by_the_datas():
    _client, answer = asked({"filter": {"name_group": ["M 31", "NGC 891"]}, "text": None, "ignored": []})
    assert answer.filter == {"name_group": ["M31", "NGC891"]}


@pytest.mark.parametrize("raw", [
    pytest.param({"filter": {"type": ["Galaxy"]}, "text": None, "ignored": []}, id="unknown type"),
    pytest.param({"filter": {"aperture": [200, 100]}, "text": None, "ignored": []}, id="range upside down"),
    pytest.param({"filter": {"finding": ["error"]}, "text": None, "ignored": []}, id="key the model was not given"),
    pytest.param({"text": "x"}, id="no filter"),
    pytest.param([], id="not an object"),
])
def test_an_invalid_answer_is_rejected(raw):
    with pytest.raises(AiError):
        answer_of(raw, COLLECTION)


def test_the_prompt_has_the_date_the_observers_and_the_catalogues():
    client, _answer = asked({"filter": {}, "text": None, "ignored": []}, "Was habe ich letztes Jahr gesehen?")
    system, user = client.questions[0]
    assert user["content"] == "Question: Was habe ich letztes Jahr gesehen?"
    for part in ("Today is 2026-11-21", "anna: Anna Example", "me: Me Myself", "own.json, wds.json", "Gx galaxy",
                 "thin galaxy: size_ratio [5, null]", "private_grade of a double star"):
        assert part in system["content"]


def test_the_schema_offers_only_the_known_values():
    filter_schema = schema(["own.json"], ["anna"])["properties"]["filter"]
    filter_properties = {key: value["anyOf"][0] for key, value in filter_schema["properties"].items()}
    assert filter_schema["required"] == list(filter_schema["properties"])
    assert all(value["anyOf"][1] == {"type": "null"} for value in filter_schema["properties"].values())
    assert filter_properties["observer"]["items"]["enum"] == ["anna"]
    assert filter_properties["catalogue"]["items"]["enum"] == ["own.json"]
    assert "UMa" in filter_properties["constellation"]["items"]["enum"]
    assert filter_properties["public_grade"]["items"]["enum"] == ["EASY", "MEDIUM", "HARD", "FAILED"]
    assert "finding" not in filter_properties and "name_pattern" not in filter_properties
    assert "observer" not in schema([], [])["properties"]["filter"]["properties"]


def test_observers_are_listed_once_whatever_their_aliases():
    observers = Observers("o.json", [Observer(id="anna", firstname="A", surname="E", aliases=("anna-old",))], [])
    assert [o.id for o in observers] == ["anna"]


def test_an_answer_that_is_not_json_is_a_question_error():
    client = FakeClient()

    def cut_off(model, messages, schema, max_tokens=None):
        assert max_tokens == 800
        raise AiAnswerError("the chat model did not answer with JSON")
    client.chat_json = cut_off
    with pytest.raises(QuestionError, match="did not answer with JSON"):
        ask(client, "chat", "Galaxien", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
