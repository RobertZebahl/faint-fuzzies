"""The word lists that correct a Question's first step."""
import pytest

from faint_fuzzies.ai.corrections import binoculars_in, corrected, is_type_word, with_binoculars
from faint_fuzzies.domain.filters import FilterKey as K


@pytest.mark.parametrize("question", ["Galaxien, die nur mit indirektem Sehen erkennbar waren",
                                      "Superthin galaxies observed with binoculars", "Emissionsnebel in Orion",
                                      "Kugelsternhaufen seit 2020", "Double stars I split"])
def test_a_kind_of_object_adds_type(question):
    assert K.TYPE in corrected(question, ())


@pytest.mark.parametrize("question", ["Welche Objekte habe ich beobachtet?", "Objects observed in 2023",
                                      "Meine Beobachtungen von M 51"])
def test_no_kind_of_object_adds_no_type(question):
    assert K.TYPE not in corrected(question, ())


def test_a_small_telescope_is_an_aperture_not_an_optic_type():
    keys = corrected("Double stars where colours were seen in a small telescope", (K.TYPE, K.OPTIC_TYPE))
    assert keys == (K.TYPE, K.APERTURE)


def test_an_instrument_keeps_its_optic_type():
    assert corrected("Galaxien mit dem Fernglas", (K.OPTIC_TYPE,)) == (K.OPTIC_TYPE, K.TYPE)


def test_the_words_of_a_lists_name_are_that_lists():
    keys = corrected("Objekte der Liste Deep Sky mit dem Fernglas, die noch nicht beobachtet wurden",
                     (K.OPTIC_TYPE, K.SEEN))
    assert keys == (K.SEEN, K.PROJECT)


@pytest.mark.parametrize("question", ["Noch nicht beobachtete Galaxien im Großen Bären", "Offene Haufen in der Kassiopeia",
                                      "Planetarische Nebel im Schwan", "Doppelsterne in Cyg", "Galaxies in Ursa Major"])
def test_a_named_constellation_is_kept(question):
    assert K.CONSTELLATION in corrected(question, (K.CONSTELLATION,))


@pytest.mark.parametrize("question", ["Bright planetary nebulae seen in summer", "Galaxien, nur indirekt gesehen",
                                      "Dunkelwolken in der Milchstraße"])
def test_a_constellation_nobody_named_is_dropped(question):
    assert K.CONSTELLATION not in corrected(question, (K.CONSTELLATION,))


@pytest.mark.parametrize("name, kind", [("Galaxien", True), ("double stars", True), ("Ringnebel", True),
                                        ("M 31", False), ("Albireo", False), ("Orion Nebula", False)])
def test_a_word_for_a_kind_of_object(name, kind):
    assert is_type_word(name) is kind


def test_an_observers_full_name_adds_observer():
    names = ("Mark McCarthy", "Uwe Pilz")
    assert K.OBSERVER in corrected("Galaxien, die Mark McCarthy fotografiert hat", (K.NAME_GROUP,), names)
    assert K.OBSERVER in corrected("Uwe Pilzs Skizzen", (), names)
    assert K.OBSERVER not in corrected("Galaxien von Mark", (), names)


@pytest.mark.parametrize("question, codes", [("mit einem 16x70 Fernglas", ["B,16x70"]),
                                             ("with my 8 x 42 and 15×70 binoculars", ["B,8x42", "B,15x70"]),
                                             ("Galaxien mit 102 mm", [])])
def test_binoculars_are_found_by_their_power_and_aperture(question, codes):
    assert binoculars_in(question) == codes


def test_named_binoculars_replace_the_optic_type_and_aperture():
    spec = {"scope": ["OWNER"], "optic_type": ["binoculars"], "aperture": [70, 70]}
    assert with_binoculars("Welche Objekte habe ich mit einem 16x70 Fernglas beobachtet?", spec) == {
        "scope": ["OWNER"], "optic": ["B,16x70"]}
    assert with_binoculars("Galaxien mit dem Fernglas", spec) == spec
