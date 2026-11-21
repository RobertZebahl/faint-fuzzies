"""The word lists that correct a Question's first step."""
import pytest

from faint_fuzzies.ai.corrections import corrected, is_type_word
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
