"""What the detail panel says about an Object itself (ui/facts.py: object_facts): everything its record holds, in
words and units, only what is there, and for a double star what it takes from the entry it references, with that
catalogue named."""
import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.references import References
from faint_fuzzies.ui.facts import object_facts
from tests.unit.builders import FIXTURES, write_catalogue

FACTS = [
    {"NAME": "Test Galaxy, TG1", "TYPE": "Gx", "CONSTELLATION": "Cet", "COORDINATES": "010203.40,+020304.50",
     "EQUINOX": "J2000.0", "MAGNITUDE": "v10.3,b11.0", "SIZE": "8.0,5.0,164", "DSS": "dss2red,20",
     "NOTES": "a private note", "DESCRIPTION": "a text", "DISABLE_DSS": True, "PUBLISH_WITHOUT_OBSERVATION": True,
     "FOO": "bar"},
    {"NAME": "Test Star", "TYPE": "*,C*", "CONSTELLATION": "Lyr", "COORDINATES": "180000.00,-451530.25",
     "MAGNITUDE": "v5.0-6.0,P350.5", "RED_STARS_LIST": True},
    {"NAME": "Own Double", "TYPE": "**", "CONSTELLATION": "And", "COORDINATES": "023300.00,+123400",
     "MAGNITUDE": "v6.0 ; v8.0", "COMPONENT": "AB,12.5,220,2020", "RATING": 1, "PROJECT_DOUBLE_STARS_LISTS": "B"},
    {"NAME": "Plain", "TYPE": "OC"},
]
LISTS = FIXTURES / "lists"
PROBLEMS = FIXTURES / "problems_datadir" / "observations" / "owner" / "objects.json"


@pytest.fixture(scope="module")
def facts_file(tmp_path_factory):
    return write_catalogue(tmp_path_factory.mktemp("facts"), "facts.json", FACTS)


def facts_of(name, own, other=None, invalid=False):
    """[(label, value, source)] of the Object of the own catalogue file `own` with this label. `other` is a second
    catalogue file to reference; `invalid` looks among the Invalid Objects, which have no references."""
    catalogues = [load_catalogue(own)]
    if other:
        catalogues.append(load_catalogue(other, check_values=False))
    pool = catalogues[0].invalid if invalid else catalogues[0].objects
    obj = next(o for o in pool if o.label == name)
    references = None if invalid else References(Collection(catalogues))
    return [(f.label, f.value, f.source) for f in object_facts(obj, references)]


def _by_label(facts):
    return {label: value for label, value, _source in facts}


def test_the_record_is_shown_in_words_and_units(facts_file):
    found = _by_label(facts_of("Test Galaxy", facts_file))
    assert found["Record"] == "facts.json, number 1"
    assert found["Type"] == "Gx (Galaxy)"
    assert found["Constellation"] == "Cet"
    assert found["Coordinates"] == "01h 02m 03.40s, +02° 03′ 04.50″"
    assert found["Equinox"] == "J2000.0"
    assert found["Magnitude"] == "v10.3, b11.0"
    assert found["Size"] == "8.0′ × 5.0′, position angle 164°"
    assert found["DSS image"] == "dss2red, field of view 20′"
    assert found["Notes"] == "a private note"
    assert found["Description"] == "a text"


def test_marks_are_listed_one_by_one(facts_file):
    marks = [value for label, value, _source in facts_of("Test Galaxy", facts_file) if label == "Mark"]
    assert marks == ["no DSS image", "published without an observation"]


def test_an_attribute_the_tool_does_not_know_is_listed_as_it_is(facts_file):
    assert ("FOO", "bar", "") in facts_of("Test Galaxy", facts_file)


def test_several_types_and_a_red_star(facts_file):
    found = _by_label(facts_of("Test Star", facts_file))
    assert found["Type"] == "* (Star), C* (Carbon star)"
    assert found["Red star"] == "yes"
    assert found["Magnitude"] == "v5.0-6.0, P350.5"
    assert found["Coordinates"] == "18h 00m 00.00s, -45° 15′ 30.25″"


def test_a_double_star_shows_its_component_and_both_magnitudes(facts_file):
    found = _by_label(facts_of("Own Double", facts_file))
    assert found["Magnitude"] == "v6.0 / v8.0"
    assert found["Component"] == "AB"
    assert found["Separation"] == "12.5″"
    assert found["Position angle"] == "220°"
    assert found["Measured in"] == "2020"
    assert found["Rating"] == "★☆☆ (1 of 3)"
    assert found["Double Stars lists"] == "binoculars (B)"


def test_a_double_star_takes_what_it_lacks_from_the_entry_it_references():
    """The pair HDS2753 has only its component; the WDS has the separation, the angle and the year."""
    facts = facts_of("HDS2753", LISTS / "own.json", LISTS / "wds.json")
    assert ("Separation", "0.4″", "wds.json") in facts
    assert ("Position angle", "139°", "wds.json") in facts
    assert ("Measured in", "2011", "wds.json") in facts
    assert ("Component", "Aa-Ab", "") in facts
    assert ("Group", "2 Sge", "") in facts
    assert ("References", "wds.json: HDS2753", "") in facts


def test_a_value_of_the_object_itself_is_not_taken_from_elsewhere():
    facts = facts_of("HDS2753", LISTS / "own.json", LISTS / "wds.json")
    assert ("Coordinates", "19h 24m 22.00s, +16° 56′ 00″", "") in facts


def test_only_what_is_there_is_shown(facts_file):
    assert facts_of("Plain", facts_file) == [("Record", "facts.json, number 4", ""), ("Type", "OC (Open cluster)", "")]


def test_an_invalid_object_shows_what_could_be_read_of_it():
    """Its type is unknown, so it is not shown; it has no references."""
    labels = [label for label, _value, _source in facts_of("Unknown Type", PROBLEMS, invalid=True)]
    assert labels == ["Record", "Constellation", "Coordinates"]
