"""Sorting the Objects browse table by Magnitude and by Size / Separation (ui/browse.py: _magnitude_value, _size_value,
_OBJECT_SORT_METHOD). Both columns show text ("v10.5", "12.3' x 4.1'", "8.2 / 9.7") but sort by a number of their
own, so 9.1 comes before 10.2 rather than after it. Sizes and separations sort together, in arcseconds. An Object
without a value sorts last whichever way the column is sorted; every other column sorts as Quasar's own sort does.
"""
import json
import shutil
import subprocess

import pytest

from faint_fuzzies.ui.browse import _OBJECT_SORT_METHOD, OBJECT_COLUMNS, _magnitude_value, _size_value
from tests.unit.builders import find_object, load_catalogues, write_catalogue

RECORDS = [
    {"NAME": "GX1", "TYPE": "Gx", "MAGNITUDE": "v10.5", "SIZE": "3.2,1.1"},
    {"NAME": "GX2", "TYPE": "Gx", "MAGNITUDE": "b12.9,v12.1"},
    {"NAME": "VAR1", "TYPE": "*,V*", "MAGNITUDE": "v4.1-6.2"},
    {"NAME": "NONE1", "TYPE": "Gx"},
    {"NAME": "DS1", "TYPE": "**", "MAGNITUDE": "v8.2;v9.7", "COMPONENT": "AB,12.3,100,2020"},
    {"NAME": "DS2", "TYPE": "**", "COMPONENT": "AB"},
]


@pytest.fixture(name="world", scope="module")
def world_fixture(tmp_path_factory):
    path = write_catalogue(tmp_path_factory.mktemp("sorting"), "own.json", RECORDS)
    return load_catalogues(path)


@pytest.mark.parametrize(("label", "expected"), [
    ("GX1", 10.5),
    ("GX2", 12.1),  # the visual value the column shows, not the first one
    ("VAR1", 4.1),  # a range sorts by its first end
    ("DS1", 8.2),  # a double star by its primary
    ("NONE1", None),
    ("DS2", None),
])
def test_the_magnitude_column_sorts_by_the_number_it_shows(world, label, expected):
    collection, references = world
    assert _magnitude_value(find_object(collection, label), references) == expected


@pytest.mark.parametrize(("label", "expected"), [
    ("GX1", 3.2 * 60),  # SIZE's major diameter, from arcminutes into arcseconds
    ("DS1", 12.3),  # a separation is already in arcseconds
    ("NONE1", None),
    ("DS2", None),  # a pair without a separation of its own, and no WDS to read one from
])
def test_the_size_column_sorts_sizes_and_separations_together_in_arcseconds(world, label, expected):
    collection, references = world
    assert _size_value(find_object(collection, label), references) == pytest.approx(expected)


@pytest.mark.parametrize(("column", "field"), [("magnitude", "magnitude_value"), ("size", "size_value")])
def test_the_columns_sort_by_their_numeric_field(column, field):
    assert next(c["field"] for c in OBJECT_COLUMNS if c["name"] == column) == field


ROWS = [
    {"names": "b", "magnitude_value": 9.1, "size_value": None, "finding_rank": 0},
    {"names": "A", "magnitude_value": None, "size_value": 600, "finding_rank": 2},
    {"names": "c", "magnitude_value": 10.2, "size_value": 12.5, "finding_rank": 1},
    {"names": "d", "magnitude_value": 2.0, "size_value": 30, "finding_rank": None},
]


def _sorted_names(column, descending):
    """The `names` of ROWS after the table's own sort method (JavaScript, run by Node) sorts them by `column`."""
    script = (f"const sort = {_OBJECT_SORT_METHOD};\n"
              f"console.log(sort({json.dumps(ROWS)}, {json.dumps(column)}, {json.dumps(descending)})"
              ".map(row => row.names).join(''));")
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js to run the table's JavaScript sort method")
@pytest.mark.parametrize(("column", "descending", "expected"), [
    ("magnitude", False, "dbcA"),  # 2.0, 9.1, 10.2, then the one without
    ("magnitude", True, "cbdA"),  # the one without still last
    ("size", False, "cdAb"),
    ("size", True, "Adcb"),
    ("names", False, "Abcd"),  # text, without regard to case
    ("finding", False, "dbcA"),  # any other column: a missing value first when ascending, as in Quasar's own sort
    ("finding", True, "Acbd"),
])
def test_the_sort_method_puts_a_missing_magnitude_or_size_last_either_way(column, descending, expected):
    assert _sorted_names(column, descending) == expected
