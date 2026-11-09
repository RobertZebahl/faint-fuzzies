"""References (domain/references.py): direct, name-based links between Objects of different catalogues.

The fixtures refs_own.json and refs_other.json hold the same things under slightly different names (the other one
plays the WDS for name matching only - it is not named "wds", so it is never trusted to fill in a missing attribute),
refs_third.json one more Object. A pair's own data is only ever borrowed from a catalogue named exactly "wds.json".
"""
import json

import pytest

from faint_fuzzies.checks import reference_findings
from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from faint_fuzzies.domain.model import ObjectAttribute
from tests.unit.builders import FIXTURES, load_catalogues, write_catalogue

OWN, OTHER, THIRD = (FIXTURES / name for name in ("refs_own.json", "refs_other.json", "refs_third.json"))
MEMBERS = (FIXTURES / "refs_members_own.json", FIXTURES / "refs_members_other.json")


def _pair(name, component="AB"):
    return {"NAME": name, "TYPE": "**", "CONSTELLATION": "Lyr", "COMPONENT": component}


# RIGHT1's second name AMBIG1 matches two WDS pairs, its first name only one; DUAL1 is in the WDS and in other.json.
PAIR_AMBIGUOUS = {
    "own.json": [_pair("RIGHT1, AMBIG1"), _pair("DUAL1")],
    "wds.json": [_pair("RIGHT1, AMBIG1"), _pair("WRONG1, AMBIG1"), _pair("DUAL1")],
    "other.json": [_pair("DUAL1")],
}


def _hds2753(component):
    """The own catalogue's HDS2753 with COMPONENT `component`, and its WDS pair with a separation of 0.1."""
    return {
        "own.json": [{"NAME": "HDS2753, 2 Sge", "GROUP": "2 Sge", "TYPE": "**", "CONSTELLATION": "Sge",
                      "COMPONENT": component}],
        "wds.json": [{"NAME": "HDS2753, 2 Sge, WDS19484+1655", "GROUP": "WDS19484+1655, 2 Sge", "TYPE": "**",
                      "CONSTELLATION": "Sge", "COMPONENT": "Aa-Ab,0.1,163,1978"}],
    }


def _write(directory, catalogues):
    """Writes {file name: records}; returns the paths, in that order."""
    return [write_catalogue(directory, name, records) for name, records in catalogues.items()]


def _label(obj):
    return obj.catalogue + ":" + (list(obj.names) or list(obj.groups))[0]


def _matches(spec, *paths):
    collection, references = load_catalogues(*paths)
    return filter_objects(collection, FilterSpec.from_dict(json.loads(spec)), references), references


def _reference_map(*paths):
    """"catalogue:first name" of every Object -> the sorted "catalogue:first name" of what it references."""
    matches, references = _matches("{}", *paths)
    return {_label(m.object): sorted(_label(r) for r in references.of(m.object)) for m in matches}


def _group_reference_map(*paths):
    """Like _reference_map, for the group records only (their labels are unique)."""
    matches, references = _matches('{"is_group": true}', *paths)
    return {m.object.catalogue + ":" + m.object.groups[0]: sorted(_label(r) for r in references.of(m.object))
            for m in matches}


def _hds2753_by_catalogue(*paths):
    matches, references = _matches('{"name": "HDS2753"}', *paths)
    return {m.object.catalogue: m.object for m in matches}, references


@pytest.fixture(scope="module")
def two():
    return _reference_map(OWN, OTHER)


@pytest.fixture(scope="module")
def three():
    return _reference_map(OWN, OTHER, THIRD)


@pytest.mark.parametrize(("key", "expected"), [
    ("refs_own.json:M 31", ["refs_other.json:M31"]),
    ("refs_other.json:M31", ["refs_own.json:M 31"]),
])
def test_names_link_objects_across_catalogues(two, key, expected):
    """"M 31" and "M31", "NGC224" and "NGC 224" only differ by the first space."""
    assert two[key] == expected


@pytest.mark.parametrize("key", ["refs_own.json:H5 82", "refs_other.json:H58 2"])
def test_a_space_in_a_name_is_ignored_only_once(two, key):
    """"H5 82" and "H58 2" are different objects; only the first space may be ignored."""
    assert two[key] == []


@pytest.mark.parametrize(("key", "expected"), [
    ("refs_own.json:2 Sge", ["refs_other.json:WDS19484+1655"]),
    ("refs_other.json:WDS19484+1655", ["refs_own.json:2 Sge"]),
])
def test_a_group_links_only_to_groups(two, key, expected):
    assert two[key] == expected


@pytest.mark.parametrize(("key", "expected"), [
    ("refs_own.json:HDS2753", ["refs_other.json:HDS2753"]),
    ("refs_own.json:STFA41", ["refs_other.json:STFA41"]),
    ("refs_own.json:STF1884", ["refs_other.json:STF1884"]),
    ("refs_other.json:HDS2753", ["refs_own.json:HDS2753"]),
    ("refs_other.json:STFA41", ["refs_own.json:STFA41"]),
    ("refs_other.json:XYZ1", []),
    ("refs_other.json:STF1884", ["refs_own.json:STF1884"]),
])
def test_a_pair_links_to_the_pair_with_the_same_component(two, key, expected):
    """All pairs of the system share the name "2 Sge", so the component decides. A pair without a component is the
    pair AB, and a pair never links to the group."""
    assert two[key] == expected


def test_a_pairs_names_are_combined_by_intersection_only_within_the_wds(tmp_path):
    """RIGHT1's name AMBIG1 alone would match two WDS pairs; its other name, RIGHT1, matches only one of them, so the
    reference is that one. A name that matches nothing in the WDS would be left out of the intersection rather than
    empty it. This applies to the WDS only: the file must be named "wds.json"."""
    own, wds, _other = _write(tmp_path, PAIR_AMBIGUOUS)
    assert _reference_map(own, wds)["own.json:RIGHT1"] == ["wds.json:RIGHT1"]


def test_a_pair_referenced_by_both_the_wds_and_another_catalogue_keeps_both(tmp_path):
    """A match in any catalogue other than the WDS is never narrowed by intersection: a pair can be catalogued in
    several external sources at once. An early version intersected across all of a pair's names regardless of the
    catalogue, which dropped Messier 40/Winnecke 4's second reference (it is in both SAC and the WDS)."""
    own, wds, other = _write(tmp_path, PAIR_AMBIGUOUS)
    assert _reference_map(own, wds, other)["own.json:DUAL1"] == sorted(["wds.json:DUAL1", "other.json:DUAL1"])


def test_resolved_separation_falls_back_to_the_reference(tmp_path):
    """The own HDS2753 has no separation of its own (its COMPONENT is just "Aa-Ab"); it is read from its WDS
    reference instead - for both catalogues' copies of the pair, since each one's reference is the other."""
    by_catalogue, references = _hds2753_by_catalogue(*_write(tmp_path, _hds2753("Aa-Ab")))
    assert references.resolved_separation(by_catalogue["own.json"]) == "0.1"
    assert references.resolved_separation(by_catalogue["wds.json"]) == "0.1"
    assert by_catalogue["own.json"].record["COMPONENT"] == "Aa-Ab"


def test_resolved_separation_does_not_fall_back_to_a_non_wds_reference():
    """The same pair and separation, but the second catalogue is not named "wds": it is never trusted for this."""
    by_catalogue, references = _hds2753_by_catalogue(OWN, OTHER)
    assert not references.resolved_separation(by_catalogue["refs_own.json"])
    assert references.resolved_separation(by_catalogue["refs_other.json"]) == "0.1"


def test_an_unknown_wds_separation_falls_back_the_same_way_as_a_blank_one(tmp_path):
    """The WDS writes -1 for an unknown separation ("Aa-Ab,-1,-1,-1") - never a real value, since a separation can't
    be negative."""
    by_catalogue, references = _hds2753_by_catalogue(*_write(tmp_path, _hds2753("Aa-Ab,-1,-1,-1")))
    assert references.resolved_separation(by_catalogue["own.json"]) == "0.1"
    assert references.resolved_separation(by_catalogue["wds.json"]) == "0.1"


def test_resolved_values_are_null_without_any_data():
    """STF1884 has no COMPONENT at all and, loaded alone, no reference to fall back to."""
    (match,), references = _matches('{"name": "STF1884"}', OWN)
    assert not references.resolved(match.object, ObjectAttribute.MAGNITUDE)
    assert not references.resolved(match.object, ObjectAttribute.COORDINATES)
    assert not references.resolved_separation(match.object)


def test_a_group_also_references_the_groups_of_its_members_partners():
    """Own group "BU17" and the WDS group "WDS02333+1234" share no name, but their members (BU17 AB and BU17 AC)
    reference each other."""
    groups = _group_reference_map(*MEMBERS)
    assert groups["refs_members_own.json:BU17"] == ["refs_members_other.json:WDS02333+1234"]
    assert groups["refs_members_other.json:WDS02333+1234"] == ["refs_members_own.json:BU17"]


def test_a_group_without_linked_members_stays_unlinked():
    groups = _group_reference_map(*MEMBERS)
    assert groups["refs_members_own.json:ZZ99"] == []
    assert groups["refs_members_other.json:WDS99999+9999"] == []


@pytest.mark.parametrize("key", ["refs_own.json:Albireo", "refs_other.json:Albireo"])
def test_objects_of_different_kinds_do_not_link(two, key):
    """A star and a double star with the same name are not the same thing."""
    assert two[key] == []


def test_objects_do_not_reference_objects_in_their_own_catalogue():
    matches, references = _matches("{}", OWN)
    assert [references.of(m.object) for m in matches] == [[]] * 7


def test_references_are_not_transitive(three):
    """The third catalogue links to the other one only; it does not reach the own catalogue."""
    assert three["refs_own.json:M 31"] == ["refs_other.json:M31"]
    assert three["refs_other.json:M31"] == ["refs_own.json:M 31", "refs_third.json:Andromedanebel"]
    assert three["refs_third.json:Andromedanebel"] == ["refs_other.json:M31"]


def test_an_object_listed_twice_under_different_types_is_referenced_twice_but_not_ambiguous(tmp_path):
    """Some official catalogues list an object twice, for example a cluster and its nebula. Both entries are
    references, and nobody can fix that, so it is not reported."""
    twice = write_catalogue(tmp_path, "refs_twice.json", [{"NAME": "NGC 224", "TYPE": "Gx", "CONSTELLATION": "And"},
                                                          {"NAME": "NGC224", "TYPE": "BN", "CONSTELLATION": "And"}])
    assert _reference_map(OWN, twice)["refs_own.json:M 31"] == ["refs_twice.json:NGC 224", "refs_twice.json:NGC224"]
    _collection, references = load_catalogues(OWN, twice)
    assert not reference_findings(references)
