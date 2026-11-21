"""Filtering on the properties of observations (domain/filters.py). All observation criteria must hold for the same
observation. The fixture observations.json holds 14 objects, in this order: NGC1055, NGC1250, NGC1, NGC2, Mond,
STF1884, STF1110, NGC752, NGC457, NGC884, IC1805, rho Cas, NGC3, NGC4."""
import pytest

from tests.unit.builders import FIXTURES, filter_cases, filter_labels, filter_matches, write_catalogue

OBSERVATIONS = FIXTURES / "observations.json"
HAS_MEDIA = [
    {"NAME": "WithPhotograph", "TYPE": "Gx", "CONSTELLATION": "Cet",
     "OBSERVATIONS": [{"OPTIC": "N,200,1200", "PHOTOGRAPH": "photo.jpg"}]},
    {"NAME": "WithSketch", "TYPE": "Gx", "CONSTELLATION": "Cet",
     "OBSERVATIONS": [{"OPTIC": "N,200,1200", "SKETCH": "sketch.jpg"}]},
    {"NAME": "WithImage", "TYPE": "Gx", "CONSTELLATION": "Cet", "OBSERVATIONS": [{"IMAGE": "header.jpg"}]},
    {"NAME": "Plain", "TYPE": "Gx", "CONSTELLATION": "Cet",
     "OBSERVATIONS": [{"OPTIC": "N,200,1200", "DESCRIPTION": "Nothing attached."}]},
]


@pytest.fixture(scope="module")
def has_media(tmp_path_factory):
    return write_catalogue(tmp_path_factory.mktemp("media"), "has_media.json", HAS_MEDIA)


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"seen": "seen"}', "NGC1055", "Mond", "STF1110", "NGC752", "NGC457", "IC1805", "NGC3", "NGC4"),
    ('{"seen": "failed"}', "NGC1250", "STF1884", "NGC884"),
    ('{"seen": "not_observed"}', "NGC1", "NGC2", "rho Cas"),
    ('{"seen": ["failed", "not_observed"]}', "NGC1250", "NGC1", "NGC2", "STF1884", "NGC884", "rho Cas"),
))
def test_seen_status_follows_the_private_observations(spec, expected):
    """Deep sky grades 1-5 are seen and 6 failed; for double stars 1-2 are seen and 3 failed. An observation without a
    grade counts as seen. Public observations do not count."""
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"public": true}', "NGC1055", "NGC2", "rho Cas"),
    ('{"public": false, "optic_type": "binoculars"}', "NGC752", "NGC457", "NGC884"),
))
def test_public_selects_public_or_private_observations(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"optic_type": "naked_eye"}', "NGC3", "NGC4"),
    ('{"public": false, "optic_type": ["binoculars", "naked_eye"]}', "NGC752", "NGC457", "NGC884", "NGC3", "NGC4"),
))
def test_optic_type_accepts_several_values(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"aperture": [null, 60]}', "NGC1055", "NGC752", "NGC457", "NGC884"),
    ('{"aperture": [80, 100]}', "NGC1055", "STF1884", "STF1110"),
    ('{"aperture": [250, null]}',),
))
def test_aperture_range_has_open_ends(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"date": ["2011-10-02", "2011-10-03"]}', "NGC1055", "NGC1250", "STF1884", "STF1110", "NGC752", "NGC3"),
    ('{"date": ["2015-01-01", null]}', "NGC4"),
    ('{"date": [null, "2011-09-29"]}', "NGC1055", "Mond", "NGC457", "NGC884", "IC1805"),
))
def test_date_range_applies_to_the_start_of_dated_observations(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"has_sketch": true}', "NGC1055"),
    ('{"public_grade": "EASY"}', "NGC1055"),
    ('{"public_grade": "hard"}', "NGC2"),
    ('{"public_grade": ["RED", "ORANGE"]}', "rho Cas"),
    ('{"public_grade": "FAILED"}',),
))
def test_sketch_and_public_grade_criteria(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"private_grade": [6, 6]}', "NGC1055", "NGC1250", "NGC884"),
    ('{"private_grade": [3, 3]}', "NGC1055", "STF1884", "NGC752", "NGC3"),
    ('{"private_grade": [5, 5]}', "NGC457", "IC1805"),
))
def test_private_grade_range_uses_the_better_end_of_an_uncertain_reading(spec, expected):
    """The private_grade criterion is numeric and independent of the scale; "seen" is scale aware."""
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"type": "**", "seen": "seen"}', "STF1110"),
    ('{"type": "**", "private_grade": [3, 3]}', "STF1884"),
    ('{"constellation": "cas", "public": false}', "NGC457", "IC1805"),
))
def test_object_and_observation_criteria_combine(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"public": true, "aperture": [80, 100]}',),
    ('{"public": false, "aperture": [80, 100]}', "NGC1055", "STF1884", "STF1110"),
))
def test_observation_criteria_must_hold_for_the_same_observation(spec, expected):
    """NGC1055 has a public observation and an 80 mm observation, but not one that is both."""
    assert filter_labels(spec, OBSERVATIONS) == expected


def test_session_filter_without_sessions_loaded_matches_nothing():
    """Without sessions no observation carries a session, so the criterion can never match."""
    assert not filter_matches('{"session": "2011-09-29T21:30"}', OBSERVATIONS)


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"has_sketch": true}', "WithSketch"),
    ('{"has_photograph": true}', "WithPhotograph"),
    ('{"has_image": true}', "WithImage"),
    ('{"has_photograph": false}', "WithSketch", "WithImage", "Plain"),
))
def test_has_sketch_photograph_and_image_criteria(has_media, spec, expected):
    assert filter_labels(spec, has_media) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"optic": "B,10x50"}', "NGC1055", "NGC457", "NGC884"),
    ('{"optic": ["b, 8x42", "R,70,400"]}', "Mond", "NGC752"),
    ('{"optic": "A"}', "NGC3", "NGC4"),
    ('{"optic": "B,10x50", "public": false, "aperture": [null, 30]}',),
))
def test_optic_names_the_instruments_themselves(spec, expected):
    assert filter_labels(spec, OBSERVATIONS) == expected


def test_an_optic_must_be_an_optic_code():
    from faint_fuzzies.domain.filters import FilterSpec, FilterSpecError
    with pytest.raises(FilterSpecError, match="invalid optic '16x70'"):
        FilterSpec.from_dict({"optic": "16x70"})
