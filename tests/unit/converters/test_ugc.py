"""The UGC converter's field rules (converters/ugc.py), on the real lines of tests/fixtures/ugc_sample.txt."""
import pytest

from faint_fuzzies.converters.ugc import convert_ugc
from tests.unit.builders import converted_sample, record_of


@pytest.fixture(scope="module")
def conversion():
    return converted_sample(convert_ugc, "ugc")


@pytest.mark.parametrize(("name", "constellation"), [
    ("UGC1", "Peg"),
    ("UGC192", "Cas"),
    ("UGC5", "Psc"),
    ("UGC7231", "Com"),
])
def test_ugc_positions_are_b1950_and_the_constellation_is_computed_from_them(conversion, name, constellation):
    assert record_of(conversion.records, name)["CONSTELLATION"] == constellation


def test_ugc_positions_name_the_equinox(conversion):
    record = record_of(conversion.records, "UGC1")
    assert record["EQUINOX"] == "B1950"
    assert record["COORDINATES"] == "000000.00,+162200"
    assert record["MAGNITUDE"] == "b14.9"


@pytest.mark.parametrize(("name", "size"), [
    ("UGC192", "10.0,10.0,"),
    ("UGC5470", "15.0,11.0,80"),
])
def test_ugc_keeps_the_larger_of_two_size_measurements(conversion, name, size):
    """Compared as numbers, not as text - comparing as text would make 8 beat 10."""
    assert record_of(conversion.records, name)["SIZE"] == size


def test_ugc_reads_the_secondary_minor_axis_with_its_own_width(conversion):
    """The secondary (red) minor axis is read with an upper bound on its field, so it never runs into the next column
    (the inclination digit, "6")."""
    assert record_of(conversion.records, "UGC7231")["SIZE"] == "10.2,2.2,155"


def test_ugc_names_include_the_mcg_designation(conversion):
    assert record_of(conversion.records, "UGC1")["NAME"] == "UGC1, MCG+03-01-015"


def test_ugc_a_suffix_names_the_appendix_object_at_the_same_number(conversion):
    record = record_of(conversion.records, "UGC1493A")
    assert record["NAME"] == "UGC1493A, MCG+08-04-000"
    assert record["CONSTELLATION"] == "Per"


def test_ugc_missing_minute_fraction_counts_as_zero_seconds(conversion):
    assert record_of(conversion.records, "UGC115")["COORDINATES"] == "001000.00,+880600"


def test_ugc_southern_declination_keeps_its_sign(conversion):
    assert record_of(conversion.records, "UGC5")["COORDINATES"] == "000036.00,-021100"


def test_ugc_without_magnitude_or_size_has_neither(conversion):
    record = record_of(conversion.records, "UGC4008")
    assert "SIZE" not in record
    assert record["MAGNITUDE"] == "b14.3"
