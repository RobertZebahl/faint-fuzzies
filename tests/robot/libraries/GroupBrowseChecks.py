# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""Group marking and member-expansion of the Objects browse table (ui/browse.py: _group_columns, _member_row,
_object_row; domain/collection.py: Collection.members_of) - without a browser. A member row uses the same
columns as the flat table's own row (_object_row), so its fields are checked the same way.

Fixture "component_datadir": SYS1 is a Group with members AAA1 (AB) and BBB2 (CD); AAA1 itself is a pair, not
a Group, and has no members of its own.
"""
from pathlib import Path

from faint_fuzzies.domain.filters import FilterSpec
from faint_fuzzies.domain.filters import filter_objects as _filter_objects
from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from faint_fuzzies.ui.browse import _group_columns, _group_links, _member_row, _object_row


def _load(data_dir):
    root = Path(data_dir)
    return load_data_dir(root, load_static_catalogues(root))


def _find(collection, label):
    """The Object named `label`, or - for a Group, which has no names of its own - the one whose GROUP is
    `label`."""
    for obj in collection.objects:
        if label in obj.names or (not obj.names and label in obj.groups):
            return obj
    raise KeyError(label)


def members_of(data_dir, label):
    """The first name of every member of the Group `label`, sorted - empty for anything that is not itself
    a Group (see Collection.members_of)."""
    data = _load(data_dir)
    obj = _find(data.collection, label)
    return sorted(m.names[0] for m in data.collection.members_of(obj))


def group_columns_of(data_dir, label):
    data = _load(data_dir)
    obj = _find(data.collection, label)
    columns = _group_columns(obj, data.collection, data.references, data.findings)
    return {
        "is_group": columns["is_group"],
        "group_rank": columns["group_rank"],
        "has_tooltip": bool(columns["group_tooltip"]),
        "member_count": len(columns["members"]),
    }


def member_row_names_its_object(data_dir, label):
    """A member row's "names" field is the member's own display name, in its own column - what the expansion
    shows next to its finding icon."""
    data = _load(data_dir)
    obj = _find(data.collection, label)
    row = _member_row(obj, data.references, data.findings)
    return row["names"] == obj.display_name and row["id"] == id(obj)


def member_row_component(data_dir, label):
    """A member row's own "component" column - what tells one member of a group apart from another (see
    ui/browse.py: _member_row), in the same column the flat Objects table itself uses (_object_row)."""
    data = _load(data_dir)
    obj = _find(data.collection, label)
    return _member_row(obj, data.references, data.findings)["component"]


def group_links_of(data_dir, label):
    """[(name, href)] of the Group fact's value for the Object named `label` - the address of the Group Object
    a name names, empty when the name is a Group name with no Group Object of its own, or more than one (see
    ui/browse.py: _group_links)."""
    data = _load(data_dir)
    obj = _find(data.collection, label)
    return _group_links(obj, data.collection)


def object_row_component(data_dir, label):
    """The "component" field of `label`'s row in the (flat, top-level) Objects table - blank when its record
    gives no COMPONENT, whatever kind of Object it is (see ui/browse.py: _object_row, names.component_name)."""
    data = _load(data_dir)
    matches = _filter_objects(data.collection, FilterSpec.from_dict({}), data.references, data.observers)
    match = next(m for m in matches if label in m.object.names)
    return _object_row(match, data.collection, data.references, data.findings)["component"]
