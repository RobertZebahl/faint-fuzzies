# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import GROUP, OTHER


def found_by(catalogue, kind, name):
    """The first names of the Objects of `catalogue` found under `name` (each once; the index may repeat
    one), and how many groups and members the collection knows under it."""
    collection = Collection([load_catalogue(Path(catalogue))])
    kinds = {"other": OTHER, "group": GROUP}
    labels = sorted({id(o): o.label for o in collection.names.lookup(kinds[kind], name)}.values())
    return labels, len(collection.groups_named(0, name)), len(collection.members_named(0, name))
