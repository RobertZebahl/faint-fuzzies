# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.lists import LISTS, WEBSITE_SUBLISTS, build_list, website_count
from faint_fuzzies.domain.references import References


def website_lists(*catalogues):
    """Builds the global list over the catalogues (the own one first) and returns {list name: (the sorted
    first names of its entries, the number the menu shows for it)} for every website list."""
    collection = Collection([load_catalogue(Path(path)) for path in catalogues])
    result = build_list(LISTS["global"], collection, References(collection))
    members = {name: sorted((e.unit.names or e.unit.groups)[0] for e in result.entries if name in e.sublists)
               for name in WEBSITE_SUBLISTS}
    return {name: (labels, website_count(name, result.entries)) for name, labels in members.items()}
