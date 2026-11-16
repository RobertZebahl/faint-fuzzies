"""The SAC converter's field rules (converters/sac.py), on the real lines of tests/fixtures/sac_sample.txt."""
import pytest

from faint_fuzzies.converters.sac import convert_sac
from tests.unit.builders import converted_sample, record_of


@pytest.fixture(scope="module")
def conversion():
    return converted_sample(convert_sac, "sac")


def test_sac_result_is_in_natural_name_order(conversion):
    assert [r["NAME"].split(", ")[0] for r in conversion.records] == [
        "3C48", "IC2177", "NGC5", "NGC9", "NGC10", "NGC44", "NGC206", "NGC2973", "PK130-11.1"]
    assert conversion.summary == "converted 9 objects"


@pytest.mark.parametrize(("name", "coordinates"), [
    ("3C48", "013736.00,+330900"),
    ("PK130-11.1", "013718.00,+502800"),
])
def test_sac_right_ascension_counts_fractions_of_a_minute(conversion, name, coordinates):
    """"01 37.6" is 37 minutes and 0.6 minutes, which are 36 seconds."""
    assert record_of(conversion.records, name)["COORDINATES"] == coordinates


@pytest.mark.parametrize(("name", "types"), [
    ("NGC206", "OC,BN,EG"),
    ("NGC44", "**"),
    ("3C48", "Q"),
    ("NGC5", "Gx"),
])
def test_sac_types_are_mapped(conversion, name, types):
    assert record_of(conversion.records, name)["TYPE"] == types


def test_sac_type_without_a_mapping_leaves_out_the_attribute(conversion):
    assert "TYPE" not in record_of(conversion.records, "NGC2973")


@pytest.mark.parametrize(("name", "size"), [
    ("PK130-11.1", "0.1,,"),
    ("IC2177", "20.0,20.0,"),
    ("NGC5", "1.2,0.7,115"),
])
def test_sac_sizes_are_arcminutes(conversion, name, size):
    """"6 s" is 0.1 arcminutes; a missing measurement stays empty."""
    assert record_of(conversion.records, name)["SIZE"] == size


def test_sac_magnitude_99_9_means_unknown(conversion):
    assert "MAGNITUDE" not in record_of(conversion.records, "NGC44")
    assert record_of(conversion.records, "3C48")["MAGNITUDE"] == "v16.5"


def test_sac_names_include_the_other_names_without_spaces(conversion):
    assert record_of(conversion.records, "IC2177")["NAME"] == "IC2177, Gum2, Sh2-296, RCW1"


@pytest.mark.parametrize(("name", "constellation"), [
    ("3C48", "Tri"),
    ("NGC44", "And"),
    ("NGC2973", "Ant"),
])
def test_sac_constellations_are_normalised_to_mixed_case(conversion, name, constellation):
    """The source writes them upper case ("TRI", "AND", "ANT"); every converter normalises through the one mapping in
    converters.common, whatever case the source used."""
    assert record_of(conversion.records, name)["CONSTELLATION"] == constellation
