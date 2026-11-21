"""Questions (faint_fuzzies.ai.question) with the chat model of tests/unit/ai/fakes.py, which gives the answer a
test sets, over stand-in Objects that only have names and groups."""
from datetime import date
from types import SimpleNamespace

import pytest

from faint_fuzzies.ai import AiAnswerError, AiError
from faint_fuzzies.ai.constellations import CONSTELLATION_NAMES
from faint_fuzzies.ai.question import Answer, Context, QuestionError, answer_of, ask, resolve_names, schema
from faint_fuzzies.domain.formats import CONSTELLATIONS
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
    assert answer == Answer({"type": ["Gx"], "aperture": [None, 102]}, "Details gesehen", (), ("type", "aperture"))


def test_criteria_that_ask_for_nothing_are_dropped():
    _client, answer = asked({"filter": {"type": ["Gx"], "constellation": [], "magnitude": [None, None],
                                        "observer": None}, "text": " ", "ignored": ["", "im Winter"]})
    assert (answer.filter, answer.text, answer.ignored) == ({"type": ["Gx"]}, None, ("im Winter",))


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
    filter_properties = schema(["own.json"], ["anna"])["properties"]["filter"]["properties"]
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
        assert max_tokens == 200  # the first step's limit
        raise AiAnswerError("the chat model did not answer with JSON")
    client.chat_json = cut_off
    with pytest.raises(QuestionError, match="did not answer with JSON"):
        ask(client, "chat", "Galaxien", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))


def test_the_second_step_offers_only_the_criteria_the_first_picked():
    client = FakeClient()
    client.criteria = ["type", "aperture", "type", "no_such_criterion"]
    seen = []
    original = client.chat_json

    def spy(model, messages, schema, max_tokens=None):
        seen.append((messages, schema))
        return original(model, messages, schema, max_tokens)
    client.chat_json = spy
    client.answer = {"filter": {"type": ["Gx"], "aperture": [None, 102]}, "text": None, "ignored": []}
    answer = ask(client, "chat", "Galaxien bis 4 Zoll", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    assert answer.criteria == ("type", "aperture")
    (_choice, _choice_schema), (messages, fill) = seen
    assert fill["properties"]["filter"]["required"] == ["type", "aperture"]
    assert list(fill["properties"]["filter"]["properties"]) == ["type", "aperture"]
    assert "- aperture:" in messages[0]["content"] and "- has_sketch:" not in messages[0]["content"]


def test_with_no_criterion_picked_the_filter_stays_empty():
    client = FakeClient()
    client.criteria = []
    client.answer = {"filter": {}, "text": "Spiralarme", "ignored": []}
    answer = ask(client, "chat", "Wo sah ich Spiralarme?", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    assert (answer.filter, answer.text, answer.criteria) == ({}, "Spiralarme", ())
    assert "none: the filter stays empty" in client.questions[0][0]["content"]


def test_the_first_step_shows_every_criterion_and_the_examples_choices():
    client = FakeClient()
    ask(client, "chat", "Galaxien", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    prompt = client.choices[0][0]["content"]
    assert "- has_sketch:" in prompt and "- private_grade:" in prompt
    assert '{"criteria": ["type", "scope", "aperture"]}' in prompt
    assert "project-deep-sky-with-binoculars" in prompt


def test_every_constellation_has_its_latin_and_german_name():
    assert set(CONSTELLATION_NAMES) == set(CONSTELLATIONS.values())
    assert CONSTELLATION_NAMES["Cyg"] == ("Cygnus", "Schwan")


@pytest.mark.parametrize("criteria, shown", [(["type", "constellation"], True), (["type"], False)])
def test_the_constellations_names_are_shown_only_when_one_is_asked_for(criteria, shown):
    client = FakeClient()
    client.criteria = criteria
    ask(client, "chat", "Planetarische Nebel in der Leier", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    prompt = client.questions[0][0]["content"]
    assert ("Lyr: Lyra, Leier" in prompt) is shown


def test_a_kind_of_object_given_as_a_name_is_dropped_unless_an_object_has_that_name():
    collection = fake_collection(["own.json"], [obj("M 57", "Ringnebel")])
    raw = {"filter": {"name_group": ["Galaxien", "Ringnebel"]}, "text": None, "ignored": []}
    assert answer_of(raw, collection).filter == {"name_group": ["Ringnebel"]}
    assert answer_of({**raw, "filter": {"name_group": ["Galaxien"]}}, collection).filter == {}


def test_owner_beside_a_private_grade_is_dropped():
    raw = {"filter": {"private_grade": [2, 2], "scope": ["OWNER"]}, "text": None, "ignored": []}
    assert answer_of(raw, COLLECTION).filter == {"private_grade": [2, 2]}


def test_a_rejected_answer_keeps_the_criteria_picked():
    client = FakeClient()
    client.criteria = ["name_group"]
    client.answer = {"filter": {"name_group": ["NGC 9999"]}, "text": None, "ignored": []}
    with pytest.raises(QuestionError) as caught:
        ask(client, "chat", "Beobachtungen von NGC 9999", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    assert caught.value.criteria == ("name_group",)


def test_an_observers_name_is_no_objects_name():
    raw = {"filter": {"name_group": ["Anna Example"]}, "text": None, "ignored": []}
    assert answer_of(raw, COLLECTION, ("Anna Example",)).filter == {}


def test_every_grade_but_failed_asks_for_nothing():
    raw = {"filter": {"public_grade": ["HARD", "EASY", "MEDIUM"]}, "text": None, "ignored": []}
    assert answer_of(raw, COLLECTION).filter == {}
    assert answer_of({**raw, "filter": {"public_grade": ["MEDIUM", "HARD"]}}, COLLECTION).filter == {
        "public_grade": ["MEDIUM", "HARD"]}


def test_a_named_observer_is_offered_to_the_second_step():
    client = FakeClient()
    client.criteria = ["name_group"]
    ask(client, "chat", "Beobachtungen von Anna Example", Context(COLLECTION, OBSERVERS, date(2026, 11, 21)))
    assert "- observer:" in client.questions[0][0]["content"]
