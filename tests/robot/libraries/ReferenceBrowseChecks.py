# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""References marking and reference-expansion of the Objects browse table (ui/browse.py: _reference_columns,
_member_row, _object_row; domain/references.py: References.of) - without a browser. A reference row uses the
same columns as the flat table's own row (_object_row), so its fields are checked the same way.

Fixture "datadir": the own pair "STFA41, 2 Sge" (component AB) references the WDS pair "STFA41, 2 Sge,
WDS19244+1656" (same name and component); the own Group "2 Sge" references the WDS Group "2 Sge,
WDS19244+1656" (a Group links only to Groups, see domain/references.robot). "Melotte 20" has no external catalogue
counterpart, so it has no References.
"""
from pathlib import Path

from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from faint_fuzzies.ui.browse import _reference_columns

_OWN_CATALOGUE = "objects.json"


def _load(data_dir):
    root = Path(data_dir)
    return load_data_dir(root, load_static_catalogues(root))


def _find(collection, label):
    """The own catalogue's Object named `label`, or - for a Group, which has no names of its own - the one
    whose GROUP is `label`."""
    for obj in collection.objects:
        if obj.catalogue != _OWN_CATALOGUE:
            continue
        if label in obj.names or (not obj.names and label in obj.groups):
            return obj
    raise KeyError(label)


def reference_columns_of(data_dir, label):
    data = _load(data_dir)
    obj = _find(data.collection, label)
    columns = _reference_columns(obj, data.references, data.findings)
    return {
        "has_references": columns["has_references"],
        "reference_rank": columns["reference_rank"],
        "has_tooltip": bool(columns["reference_tooltip"]),
        "reference_count": len(columns["references"]),
        "reference_catalogues": sorted({r["catalogue"] for r in columns["references"]}),
    }


def reference_row_names_its_object(data_dir, label):
    """A reference row's "names" field is the referenced Object's own display name, and its "id" is that
    Object's identity - what a click resolves against (see ui/browse.py: _on_reference_click)."""
    data = _load(data_dir)
    obj = _find(data.collection, label)
    found = data.references.of(obj)
    row = _reference_columns(obj, data.references, data.findings)["references"][0]
    return row["names"] == found[0].display_name and row["id"] == id(found[0])
