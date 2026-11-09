"""The Herschel converter's field rules (converters/herschel.py), on the real lines of
tests/fixtures/herschel_sample.txt."""
import pytest

from faint_fuzzies.converters.herschel import convert_herschel
from tests.unit.builders import converted_sample, record_of


@pytest.fixture(scope="module")
def conversion():
    return converted_sample(convert_herschel, "herschel")


def _record(conversion, name):
    return record_of(conversion.records, name)


def test_herschel_400_objects_belong_to_the_list_400(conversion):
    """The description carries the mark "400"."""
    assert _record(conversion, "H1.1, NGC1055")["GROUP"] == "400"
    assert "GROUP" not in _record(conversion, "H2.32, NGC3645")


def test_herschel_result_is_in_natural_order(conversion):
    assert [r["NAME"].split(", ")[0] for r in conversion.records][:4] == ["H1.1", "H1.7", "H1.9", "H1.10"]


def test_herschel_names_two_parts_of_a_double_object(conversion):
    assert _record(conversion, "H3.182, NGC7578, H3.182.1, H3.182.2")["TYPE"] == "Gx"


def test_herschel_marks_a_documented_cluster(conversion):
    """The source calls NGC2459 "not documented", which the tool maps to a galaxy; it is a cluster."""
    assert _record(conversion, "H3.479, NGC2459")["TYPE"] == "OC"


def test_herschel_short_line_has_only_a_name(conversion):
    assert list(_record(conversion, "H1.7")) == ["NAME"]
