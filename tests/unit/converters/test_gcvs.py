"""The GCVS converter's field rules (converters/gcvs.py), on the real lines of tests/fixtures/gcvs_sample.txt."""
import pytest

from faint_fuzzies.converters.gcvs import convert_gcvs
from tests.unit.builders import converted_sample, record_of


@pytest.fixture(scope="module")
def conversion():
    return converted_sample(convert_gcvs, "gcvs")


@pytest.mark.parametrize(("name", "magnitude"), [
    ("R And", "v5.8-15.2,P409.2"),
    ("S And", "v5.8-16.0"),
    ("AE And", "b15.1-17.6"),
    ("SS And", "p10.0-11.4,P152.5"),
])
def test_gcvs_magnitude_is_the_range_and_the_period(conversion, name, magnitude):
    assert record_of(conversion.records, name)["MAGNITUDE"] == magnitude


@pytest.mark.parametrize(("name", "magnitude"), [
    ("V0437 Car", "b9.7-9.71,P0.0043"),
    ("WW And", "v10.92-11.59,P23.285213"),
])
def test_gcvs_second_magnitude_given_as_a_difference_is_added_without_float_noise(conversion, name, magnitude):
    """Rounding avoids floating-point sums such as 9.709999999999999."""
    assert record_of(conversion.records, name)["MAGNITUDE"] == magnitude


def test_gcvs_star_without_position_or_magnitude_has_neither(conversion):
    record = record_of(conversion.records, "VV And")
    assert "COORDINATES" not in record
    assert "MAGNITUDE" not in record


def test_gcvs_position_loses_its_uncertainty_marks(conversion):
    assert record_of(conversion.records, "S And")["COORDINATES"] == "004243.1,+411605"


def test_gcvs_stars_are_variable_stars_in_the_constellation_of_their_number(conversion):
    car = record_of(conversion.records, "V0437 Car")
    assert car["TYPE"] == "*,V*"
    assert car["CONSTELLATION"] == "Car"
    assert record_of(conversion.records, "R And")["CONSTELLATION"] == "And"


def test_gcvs_has_no_fixed_number_of_header_lines(conversion):
    """A data line's NNo field (the first seven characters) is always digits, optionally followed by a component
    letter or a space, then "|" - a header or column-rule line never looks like that, whatever its number: the source
    has been seen with two header lines and with none at all."""
    assert converted_sample(convert_gcvs, "gcvs", drop_lines=2).records == conversion.records
