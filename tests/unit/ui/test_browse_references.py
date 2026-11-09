"""References marked in the Objects browse table, and a reference's target available to expand to (ui/browse.py:
_reference_columns; domain/references.py: References.of), mirroring test_browse_groups.py.

Fixture "datadir": the own pair "STFA41, 2 Sge" (component AB) references the WDS pair "STFA41, 2 Sge,
WDS19244+1656" (same name and component); the own Group "2 Sge" references the WDS Group "2 Sge, WDS19244+1656" (a
Group links only to Groups). "Melotte 20" has no external catalogue counterpart, so it has no References.
"""
import pytest

from faint_fuzzies.ui.browse import _reference_columns
from tests.unit.builders import FIXTURES, find_object, load_world


@pytest.fixture(scope="module")
def world():
    return load_world(FIXTURES / "datadir")


def _own(world, label):
    return find_object(world.collection, label, catalogue="objects.json")


def _reference_columns_of(world, label):
    columns = _reference_columns(_own(world, label), world.references, world.findings)
    return {
        "has_references": columns["has_references"],
        "reference_rank": columns["reference_rank"],
        "has_tooltip": bool(columns["reference_tooltip"]),
        "reference_count": len(columns["references"]),
        "reference_catalogues": sorted({r["catalogue"] for r in columns["references"]}),
    }


def test_a_pairs_row_is_marked_with_a_tooltip_and_the_right_reference(world):
    columns = _reference_columns_of(world, "STFA41")
    assert columns["has_references"]
    assert columns["reference_rank"] == 1
    assert columns["has_tooltip"]
    assert columns["reference_count"] == 1
    assert columns["reference_catalogues"] == ["wds.json"]


def test_a_groups_row_is_marked_too_referencing_the_wds_group(world):
    """A Group links only to Groups, the same rule that lets Group marking and reference marking coexist
    independently on one row."""
    columns = _reference_columns_of(world, "2 Sge")
    assert columns["has_references"]
    assert columns["reference_count"] == 1
    assert columns["reference_catalogues"] == ["wds.json"]


def test_an_object_with_no_counterpart_in_another_catalogue_is_not_marked(world):
    columns = _reference_columns_of(world, "Melotte 20")
    assert not columns["has_references"]
    assert columns["reference_rank"] == 0
    assert not columns["has_tooltip"]
    assert columns["reference_count"] == 0


def test_a_reference_row_names_its_own_object(world):
    """A reference row's "names" field is the referenced Object's own display name, and its "id" is that Object's
    identity - what a click resolves against (see ui/browse.py: _on_reference_click)."""
    obj = _own(world, "STFA41")
    (target, *_) = world.references.of(obj)
    row = _reference_columns(obj, world.references, world.findings)["references"][0]
    assert row["names"] == target.display_name
    assert row["id"] == id(target)
