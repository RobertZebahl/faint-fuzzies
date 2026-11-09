"""The magnitude, size, separation, rating, binocular_rating and has_notes filter criteria (domain/filters.py).

The own catalogue: MagOwn has its own MAGNITUDE; MagRef has none of its own (a double star pair, COMPONENT "AB" only)
and references the WDS's "MagRef, WDS00000+0000" (MAGNITUDE "v9.5,b10.1", COMPONENT "AB,3.2,120,2015") by shared name
and component, the same way an own-catalogue pair usually borrows from the WDS.
"""
import pytest

from tests.unit.builders import filter_cases, filter_labels, write_catalogue

OWN = [
    {"NAME": "MagOwn", "TYPE": "Gx", "CONSTELLATION": "And", "MAGNITUDE": "v11.2"},
    {"NAME": "MagRef", "TYPE": "**", "CONSTELLATION": "And", "COMPONENT": "AB"},
    {"NAME": "MagPair", "TYPE": "**", "CONSTELLATION": "And", "MAGNITUDE": "v7.5;v11.0", "COMPONENT": "AB"},
    {"NAME": "MagNone", "TYPE": "Gx", "CONSTELLATION": "And"},
    {"NAME": "BigGx", "TYPE": "Gx", "CONSTELLATION": "And", "SIZE": "10,2"},
    {"NAME": "SmallGx", "TYPE": "Gx", "CONSTELLATION": "And", "SIZE": "3,2"},
    {"NAME": "RoundGx", "TYPE": "Gx", "CONSTELLATION": "And", "SIZE": "6,5"},
    {"NAME": "CircularGx", "TYPE": "Gx", "CONSTELLATION": "And", "SIZE": "6"},
    {"NAME": "RatedHigh", "TYPE": "Gx", "CONSTELLATION": "And", "RATING": 3},
    {"NAME": "RatedLow", "TYPE": "Gx", "CONSTELLATION": "And", "RATING": 1},
    {"NAME": "BinocularHigh", "TYPE": "OC", "CONSTELLATION": "And", "PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING": 3},
    {"NAME": "NotesMatch", "TYPE": "Gx", "CONSTELLATION": "And", "NOTES": "observe again with a wider field"},
    {"NAME": "NotesOther", "TYPE": "Gx", "CONSTELLATION": "And", "NOTES": "nothing special"},
]
WDS = [
    {"NAME": "MagRef, WDS00000+0000", "TYPE": "**", "CONSTELLATION": "And", "MAGNITUDE": "v9.5,b10.1",
     "COMPONENT": "AB,3.2,120,2015"},
]


@pytest.fixture(scope="module")
def own(tmp_path_factory):
    return write_catalogue(tmp_path_factory.mktemp("filter_extended"), "filter_extended_own.json", OWN)


@pytest.fixture(scope="module")
def wds(own):
    return write_catalogue(own.parent, "filter_extended_wds.json", WDS)


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"magnitude": [11, 12]}', "MagOwn"),
    ('{"magnitude": [0, 10]}',),
))
def test_magnitude_matches_the_objects_own_value(own, spec, expected):
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"magnitude": [null, 8]}',),
    ('{"magnitude": [null, 12]}', "MagOwn", "MagPair"),
))
def test_magnitude_range_needs_every_component_of_a_double_star_in_range(own, spec, expected):
    """MagPair's own MAGNITUDE is "v7.5;v11.0" - a bright primary (7.5) but a much fainter secondary (11.0). "Brighter
    than 8" must not match it: the secondary alone would not be seen at that brightness, even though the primary
    qualifies on its own."""
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"magnitude_delta": [3, 4]}', "MagPair"),
    ('{"magnitude_delta": [0, 1]}',),
))
def test_magnitude_delta_matches_the_absolute_difference_of_a_double_stars_two_components(own, spec, expected):
    """MagPair's components are 7.5 and 11.0, a delta of 3.5. Anything without exactly two components - MagOwn has only
    one, and MagNone/MagRef (no WDS loaded here) have none at all - never matches, since there is then no difference to
    compute."""
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"magnitude": [0, 100]}', "MagOwn", "MagPair"),
))
def test_an_object_without_a_resolvable_magnitude_never_matches(own, spec, expected):
    """MagNone has no MAGNITUDE; MagRef has none of its own either and, without WDS loaded here, no reference to resolve
    one from - a wide open range still excludes both."""
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"size": [5, null]}', "RoundGx", "CircularGx"),
))
def test_size_default_is_the_smaller_of_the_two_diameters(own, spec, expected):
    """BigGx is "10,2" - a wide but narrow sliver: min(10,2)=2, so it does not qualify as "at least 5 arcminutes" even
    though its major axis is 10. RoundGx ("6,5") and CircularGx ("6", no minor of its own, treated as circular) both
    qualify: every direction of them is at least 5."""
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"rating": [2, 3]}', "RatedHigh"),
    ('{"rating": [0, 3]}', "RatedHigh", "RatedLow"),
    ('{"binocular_rating": [0, 3]}', "BinocularHigh"),
))
def test_rating_and_binocular_rating_are_two_distinct_criteria(own, spec, expected):
    """RatedHigh and RatedLow have RATING but no PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING, and BinocularHigh the other
    way round, so each criterion only ever picks up its own objects."""
    assert filter_labels(spec, own) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"has_notes": true, "name": ["NotesMatch", "NotesOther", "MagOwn"]}', "NotesMatch", "NotesOther"),
    ('{"has_notes": false, "name": ["NotesMatch", "NotesOther", "MagOwn"]}', "MagOwn"),
))
def test_has_notes_matches_whether_the_record_carries_a_non_empty_notes(own, spec, expected):
    assert filter_labels(spec, own) == expected


def test_magnitude_falls_back_to_the_reference(own, wds):
    """MagRef has no MAGNITUDE itself; it is read from the WDS pair instead (the visual value, "v9.5", is picked over
    the blue "b10.1")."""
    assert "MagRef" in filter_labels('{"magnitude": [9, 10]}', own, wds)


@pytest.mark.parametrize(("spec", "found"), [
    ('{"magnitude": {"range": [9, 10], "band": "b"}}', False),
    ('{"magnitude": {"range": [10, 11], "band": "b"}}', True),
    ('{"magnitude": {"range": [10, 11], "band": "v"}}', False),
])
def test_magnitude_band_selects_a_specific_value_instead_of_the_default_priority(own, wds, spec, found):
    """The WDS's MagRef pair has both "v9.5" and "b10.1"; without a band the default priority picks the visual value,
    but band "b" picks the blue one instead."""
    assert ("MagRef" in filter_labels(spec, own, wds)) is found


def test_size_axis_selects_one_dimension_explicitly_never_through_a_reference(own):
    """axis "major" recovers a plain major-diameter check (BigGx's 10 qualifies even though its minor is only 2); axis
    "minor" needs the minor diameter itself, so CircularGx (no minor of its own) never matches it, unlike the
    axis-less default that treats it as circular."""
    assert "BigGx" in filter_labels('{"size": {"range": [5, null], "axis": "major"}}', own)
    minor = filter_labels('{"size": {"range": [5, null], "axis": "minor"}}', own)
    assert "BigGx" not in minor
    assert "CircularGx" not in minor
    assert "RoundGx" in minor


@pytest.mark.parametrize(("spec", "found"), [('{"separation": [3, 4]}', True), ('{"separation": [0, 1]}', False)])
def test_separation_falls_back_to_the_reference(own, wds, spec, found):
    """MagRef's own COMPONENT ("AB") has no separation; 3.2 comes from the WDS pair (COMPONENT "AB,3.2,120,2015")."""
    assert ("MagRef" in filter_labels(spec, own, wds)) is found
