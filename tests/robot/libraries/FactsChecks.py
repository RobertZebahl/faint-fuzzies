# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""The facts the detail panel shows about an Object, without a browser."""
from pathlib import Path

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.references import References
from faint_fuzzies.ui.facts import object_facts


def facts_of(name, own, other=None, invalid=False):
    """[(label, value, source)] of the Object of the own catalogue file `own` with this label. `other` is a second
    catalogue file to reference; `invalid` looks among the Invalid Objects, which have no references."""
    catalogues = [load_catalogue(Path(own))]
    if other:
        catalogues.append(load_catalogue(Path(other), check_values=False))
    collection = Collection(catalogues)
    pool = catalogues[0].invalid if invalid else catalogues[0].objects
    obj = next(o for o in pool if o.label == name)
    references = None if invalid else References(collection)
    return [(f.label, f.value, f.source) for f in object_facts(obj, references)]
