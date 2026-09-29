# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.lists import LISTS, build_list
from faint_fuzzies.domain.observation import Observation, parse_optic
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.domain.references import References


def project_lists(catalogue, project, orbit_pairs=(), community=()):
    """{label of the entry: its sublists (without the right ascension bands) and its stars} for a project list
    over one catalogue. `orbit_pairs` are names of pairs that have an orbit diagram; `community` are
    (object name, observer id, import format, optic code, rating) of observations of other observers."""
    collection = Collection([load_catalogue(Path(catalogue))])
    by_name = {name: obj for obj in collection.objects for name in obj.names}
    for name, observer, format_name, optic, rating in community:
        by_name[name].community_observations.append(Observation(
            {}, public=True, optic=parse_optic(optic), visibility=(), observer=Observer(observer, "A", "B"),
            rating=int(rating), format=format_name))
    orbits = frozenset(id(by_name[name]) for name in orbit_pairs)
    result = build_list(LISTS[project], collection, References(collection), None, orbits)
    return {e.unit.label: {"lists": sorted(s for s in e.sublists if not s.startswith("ra-")),
                           "stars": e.rounded_rating} for e in result.entries}
