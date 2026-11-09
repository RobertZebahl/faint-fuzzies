"""Groups marked in the Objects browse table, and a Group's members available to expand to (ui/browse.py:
_group_columns, _member_row, _object_row, _group_links; domain/collection.py: Collection.members_of). A member row
uses the same columns as the flat table's own row (_object_row), so its fields are checked the same way.

Fixture "component_datadir": SYS1 is a Group with members AAA1 (AB) and BBB2 (CD); AAA1 itself is a pair, not a
Group, and has no members of its own.
"""
import pytest

from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from faint_fuzzies.ui.browse import _group_columns, _group_links, _member_row, _object_row
from tests.unit.builders import FIXTURES, find_object, load_world


@pytest.fixture(scope="module")
def world():
    return load_world(FIXTURES / "component_datadir")


def _members(world, label):
    return sorted(m.names[0] for m in world.collection.members_of(find_object(world.collection, label)))


def _group_columns_of(world, label):
    columns = _group_columns(find_object(world.collection, label), world.collection, world.references,
                             world.findings)
    return {
        "is_group": columns["is_group"],
        "group_rank": columns["group_rank"],
        "has_tooltip": bool(columns["group_tooltip"]),
        "member_count": len(columns["members"]),
    }


def _object_row_component(world, label):
    """The "component" field of `label`'s row in the (flat, top-level) Objects table."""
    matches = filter_objects(world.collection, FilterSpec.from_dict({}), world.references, world.observers)
    match = next(m for m in matches if label in m.object.names)
    return _object_row(match, world.collection, world.references, world.findings)["component"]


def test_a_groups_members_are_found_by_its_group_name(world):
    assert _members(world, "SYS1") == ["AAA1", "BBB2"]


def test_a_pair_is_not_a_group_and_has_no_members(world):
    assert _members(world, "AAA1") == []


def test_the_group_row_is_marked_with_a_tooltip_and_the_right_member_count(world):
    columns = _group_columns_of(world, "SYS1")
    assert columns["is_group"]
    assert columns["group_rank"] == 1
    assert columns["has_tooltip"]
    assert columns["member_count"] == 2


def test_a_pairs_row_is_not_marked_as_a_group(world):
    columns = _group_columns_of(world, "AAA1")
    assert not columns["is_group"]
    assert columns["group_rank"] == 0
    assert not columns["has_tooltip"]
    assert columns["member_count"] == 0


def test_a_member_row_names_its_own_object(world):
    obj = find_object(world.collection, "AAA1")
    row = _member_row(obj, world.references, world.findings)
    assert row["names"] == obj.display_name
    assert row["id"] == id(obj)


def test_a_member_row_names_its_own_component(world):
    """AB tells AAA1 apart from BBB2's CD, within the same expanded group - in its own column, not folded into the
    name text."""
    obj = find_object(world.collection, "AAA1")
    assert _member_row(obj, world.references, world.findings)["component"] == "AB"


def test_the_objects_table_shows_a_pairs_component(world):
    assert _object_row_component(world, "AAA1") == "AB"


def test_a_pair_without_component_shows_a_blank_component_like_the_facts_panel(world):
    assert _object_row_component(world, "PLAIN7") == ""


def test_a_members_group_name_links_to_its_group_object(world):
    """AAA1's GROUP is SYS1, the only Group Object of that name in its own catalogue: the facts panel's Group value
    links to it, at the same address the Log page links an Object by (ui/log.py: object_link)."""
    assert _group_links(find_object(world.collection, "AAA1"), world.collection) == [
        ("SYS1", "/?object=objects.json%3A1")]


def test_an_object_with_no_group_has_no_group_links(world):
    assert not _group_links(find_object(world.collection, "SOLO3"), world.collection)
