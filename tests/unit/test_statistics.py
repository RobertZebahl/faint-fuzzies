"""The Statistics: the website's table (domain/statistics.py) and the app's Statistics screen (ui/statistics.py) count
the same. In the fixture world "lists" Messier 45 has only a note, that is a Header, and 2 Sge has a note on its group
as well. A Header is never an Observation; the total counts every Object of the Global list, an observer's column the
Objects that observer observed."""
import pytest

from faint_fuzzies.cli import CommunitySource, Inputs, _load
from faint_fuzzies.domain.lists import LISTS, build_list
from faint_fuzzies.domain.statistics import CATEGORY_NAMES, MISCELLANEOUS, TOTAL, category, observer_columns, type_table
from faint_fuzzies.ui import statistics as app
from tests.unit.builders import FIXTURES

WORLD = FIXTURES / "lists"


@pytest.fixture(scope="module")
def global_list():
    sources = [CommunitySource("project-double-stars-visual", "anna-example", WORLD / "anna-example" / "visual.csv"),
               CommunitySource("project-double-stars-photographic", "anna-example",
                               WORLD / "anna-example" / "photographic.csv"),
               CommunitySource("project-double-stars-visual", "carla-example", WORLD / "carla-example" / "visual.csv"),
               CommunitySource("project-deep-sky-with-binoculars", "bert-example",
                               WORLD / "bert-example" / "visual.csv"),
               CommunitySource("global", "dana-example", WORLD / "dana-example" / "global.csv")]
    collection, references, observers, *_ = _load(Inputs(
        [WORLD / "own.json", WORLD / "wds.json"], None, WORLD / "observers.json", sources))
    return build_list(LISTS["global"], collection, references, observers), observers


def test_the_app_and_the_website_count_the_same(global_list):
    """Compares every cell, as (column, category, app, website); the app's finer categories are put together into
    Miscellaneous first."""
    result, observers = global_list
    table = type_table(result, observers)
    units = [entry.unit for entry in result.entries]
    columns = [(TOTAL, app.get_all_observation_pairs(result), units)] + [
        (column["id"], app.get_observer_pairs(result, column["id"], observers), None)
        for column in observer_columns(result, observers)]
    differences = []
    for key, pairs, objects in columns:
        stats = app.type_category_stats(pairs, objects)
        for name in CATEGORY_NAMES:
            if name == MISCELLANEOUS:
                matching = [(o, ob) for o, ob in pairs if category(o) == MISCELLANEOUS]
                found = (len({id(o) for o in (objects if objects is not None else [o for o, _ in matching])
                              if category(o) == MISCELLANEOUS}), len(matching))
            else:
                found = (stats[name]["objects"], stats[name]["observations"])
            wanted = table[name].get(key, (0, 0))
            if found != wanted:
                differences.append((key, name, found, wanted))
    tiles = result.statistics["visual_observations"] + result.statistics["photographic_observations"]
    total = sum(table[name][TOTAL][1] for name in CATEGORY_NAMES)
    if tiles != total:
        differences.append((TOTAL, "observations tile", tiles, total))
    assert not differences


def test_an_object_with_only_a_header_is_in_the_total_but_not_in_an_observers_column(global_list):
    """Messier 45 (an open cluster) has only a note: it is one of the Objects of its type in the total, but nobody
    observed it, and the note is not an observation."""
    clusters = type_table(*global_list)["open-clusters"]
    assert clusters[TOTAL][0] > max(v[0] for k, v in clusters.items() if k != TOTAL)
