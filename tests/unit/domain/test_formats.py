"""The formats of the values of a record (domain/formats.py): SIZE, MAGNITUDE, COMPONENT, DSS, EQUINOX, CONSTELLATION,
the ratings, the letters of the Double Stars lists and the flags, as the own catalogue is checked on loading (the same
findings validate reports). A value that is not in its format is an error; only a second magnitude on an object that
is not a double star and private observations out of the order of their date are warnings. Numbers are not bounded
(the WDS writes a separation of -1 for "unknown"). Fixture "values/own.json": each record's name says what is wrong
with it, and the ones ending in "Ok" are right."""
import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.names import set_object_name_abbreviations
from tests.unit.builders import FIXTURES


@pytest.fixture(scope="module")
def findings():
    set_object_name_abbreviations([])
    return load_catalogue(FIXTURES / "values" / "own.json").findings


def test_every_wrong_value_is_an_error_of_its_attribute(findings):
    errors = sorted((f.object, f.attribute) for f in findings if f.severity == "error")
    assert errors == sorted([
        ("SizeText", "SIZE"), ("SizeFour", "SIZE"), ("SizeAngleNotWhole", "SIZE"), ("SizeNumber", "SIZE"),
        ("MagLaterElement", "MAGNITUDE"), ("MagThreeParts", "MAGNITUDE"), ("MagNoLetter", "MAGNITUDE"),
        ("CompSeparationText", "COMPONENT"), ("CompFive", "COMPONENT"), ("CompAngleText", "COMPONENT"),
        ("DssUnknown", "DSS"), ("DssFovText", "DSS"),
        ("RatingTooHigh", "RATING"), ("RatingText", "RATING"), ("RatingBoolean", "RATING"),
        ("BinocularRatingTooHigh", "PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING"),
        ("ListsUnknownLetter", "PROJECT_DOUBLE_STARS_LISTS"),
        ("FlagText", "DISABLE_DSS"), ("FlagNumber", "RED_STARS_LIST"),
        ("DisableProjectDoubleStarsText", "DISABLE_PROJECT_DOUBLE_STARS"),
        ("PublishWithoutObservationNumber", "PUBLISH_WITHOUT_OBSERVATION"),
        ("EquinoxShort", "EQUINOX"), ("ConstellationWrong", "CONSTELLATION"),
    ])


def test_only_two_things_are_warnings(findings):
    warnings = sorted((f.object, f.attribute, f.message[:30]) for f in findings if f.severity == "warning")
    assert warnings == [("ObservationsOutOfOrder", "DATE", "the observations are not in th"),
                        ("SecondMagnitudeOnGalaxy", "MAGNITUDE", "a second magnitude is only for")]


@pytest.mark.parametrize(("name", "expected"), [
    ("MagLaterElement", "'x5' is none of v10.3"),
    ("RatingTooHigh", "a whole number from 0 to 3"),
    ("ConstellationWrong", "none of the 88 IAU constellations"),
    ("PublishWithoutObservationNumber", "true or false"),
])
def test_the_message_says_what_is_expected(findings, name, expected):
    assert expected in next(f.message for f in findings if f.object == name)
