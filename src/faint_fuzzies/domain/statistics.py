"""The Statistics: for each Object type, how many Objects of the Global observation list there are and how many
Observations were made of them, in total and by each Observer. The website's home page shows them; the app's
Statistics screen shows its own, finer breakdown instead (see ui/statistics.py's type_category_stats). A
Header is never counted as an Observation (see `counted_observations`)."""
from faint_fuzzies.domain.lists import ListResult, counted_observations
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.model import ObjectType as T
from faint_fuzzies.domain.observer import OWN_ID, Observers

TOTAL = "total"
MISCELLANEOUS = "miscellaneous"
# the Object types with a row of their own; every other Object, and one of several of these, is Miscellaneous
CATEGORIES = (
    ("double-stars", T.DOUBLE_STAR), ("asterisms", T.ASTERISM), ("open-clusters", T.OPEN_CLUSTER),
    ("globular-clusters", T.GLOBULAR_CLUSTER), ("planetary-nebulae", T.PLANETARY_NEBULA),
    ("bright-nebulae", T.BRIGHT_NEBULA), ("dark-nebulae", T.DARK_NEBULA), ("galaxies", T.GALAXY),
)
CATEGORY_NAMES = [name for name, _ in CATEGORIES] + [MISCELLANEOUS]


def category(obj: Object) -> str:
    """The statistics category of an Object: one of CATEGORIES' names when exactly one of them applies,
    MISCELLANEOUS otherwise (none, or more than one).

    :param obj: the object to categorize
    :returns: the category name
    """
    named = [name for name, code in CATEGORIES if code in obj.types]
    return named[0] if len(named) == 1 else MISCELLANEOUS


def observer_columns(result: ListResult, observers: Observers | None) -> list[dict[str, str]]:
    """The observers of the list, {"id", "name"}: the user first, then the others by surname.

    :param result: the list to find the observers of
    :param observers: the Observers to find the user among; OWN_ID when not given
    :returns: the observers, user first
    """
    owner_id = observers.owner_id() if observers else OWN_ID
    people = result.statistics["observers"]
    return [p for p in people if p["id"] == owner_id] + [p for p in people if p["id"] != owner_id]


def type_table(result: ListResult, observers: Observers | None) -> dict[str, dict[str, tuple[int, int]]]:
    """{category: {TOTAL or an observer's id: (Objects, Observations)}}. The total counts every Object of
    the list; an observer's column the Objects that observer observed, and the observations, each counted
    once.

    :param result: the list to tabulate
    :param observers: the Observers to resolve ids against; OWN_ID when not given
    :returns: the table
    """
    owner_id = observers.owner_id() if observers else OWN_ID
    table: dict[str, dict[str, list[int]]] = {name: {TOTAL: [0, 0]} for name in CATEGORY_NAMES}
    for entry in result.entries:
        row = table[category(entry.unit)]
        row[TOTAL][0] += 1
        counted = counted_observations(entry)
        row[TOTAL][1] += len(counted)
        for observer_id in {_observer_id(found, owner_id) for found in counted}:
            cell = row.setdefault(observer_id, [0, 0])
            cell[0] += 1
        for found in counted:
            row[_observer_id(found, owner_id)][1] += 1
    return {name: {key: (cell[0], cell[1]) for key, cell in row.items()} for name, row in table.items()}


def _observer_id(found, owner_id: str) -> str:
    observer = found.observation.observer
    return observer.id if observer else owner_id
