"""The texts of an observation as the info panel shows them (Observation.descriptions): German and English side by
side when both exist, a language mark when only one does, none when the text belongs to no language."""
import pytest

from faint_fuzzies.domain.observation import Observation


def _descriptions(record):
    return [list(pair) for pair in Observation(record, public=True, optic=None, visibility=()).descriptions]


def test_both_languages_are_shown():
    assert _descriptions({"DESCRIPTION_DE": "Deutscher Text", "DESCRIPTION_EN": "English text"}) == [
        ["DE", "Deutscher Text"], ["EN", "English text"]]


@pytest.mark.parametrize(("record", "expected"), [
    ({"DESCRIPTION_DE": "Nur deutsch"}, [["DE", "Nur deutsch"]]),
    ({"DESCRIPTION_EN": "English only"}, [["EN", "English only"]]),
])
def test_one_language_keeps_its_mark(record, expected):
    """The mark shows a reviewer that the other language is missing."""
    assert _descriptions(record) == expected


def test_the_same_text_in_both_languages_is_shown_once():
    """Another observer's single text is stored under both languages."""
    assert _descriptions({"DESCRIPTION_DE": "Same", "DESCRIPTION_EN": "Same"}) == [[None, "Same"]]


def test_a_plain_description_has_no_language():
    assert _descriptions({"DESCRIPTION": "Private note in one language"}) == [[None, "Private note in one language"]]


@pytest.mark.parametrize(("record", "expected"), [
    ({"DESCRIPTION_DE": " ", "DESCRIPTION_EN": "Text"}, [["EN", "Text"]]),
    ({}, []),
])
def test_blank_texts_are_left_out(record, expected):
    assert _descriptions(record) == expected
