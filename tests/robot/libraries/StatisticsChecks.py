# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.cli import CommunitySource, Inputs, _load
from faint_fuzzies.domain.lists import LISTS, build_list
from faint_fuzzies.domain.statistics import CATEGORY_NAMES, MISCELLANEOUS, TOTAL, category, observer_columns, type_table
from faint_fuzzies.ui import statistics as app


def _world(root):
    root = Path(root)
    sources = [CommunitySource("project-double-stars-visual", "anna-example", root / "anna-example" / "visual.csv"),
               CommunitySource("project-double-stars-photographic", "anna-example",
                               root / "anna-example" / "photographic.csv"),
               CommunitySource("project-double-stars-visual", "carla-example", root / "carla-example" / "visual.csv"),
               CommunitySource("project-deep-sky-with-binoculars", "bert-example", root / "bert-example" / "visual.csv"),
               CommunitySource("global", "dana-example", root / "dana-example" / "global.csv")]
    collection, references, observers, _community = _load(Inputs(
        [root / "own.json", root / "wds.json"], None, root / "observers.json", sources))
    return build_list(LISTS["global"], collection, references, observers), observers


def statistics_differences(root):
    """The cells in which the website's statistics (`domain.statistics`) and the numbers of the app's Statistics
    screen differ, as (column, category, app, website), and the website's table itself."""
    result, observers = _world(root)
    table = type_table(result, observers)
    units = [entry.unit for entry in result.entries]
    columns = [(TOTAL, app.get_all_observation_pairs(result), units)] + [
        (column["id"], app.get_observer_pairs(result, column["id"], observers), None)
        for column in observer_columns(result, observers)]
    differences = []
    for key, pairs, objects in columns:
        stats = app.type_category_stats(pairs, objects)
        for name in CATEGORY_NAMES:
            if name == MISCELLANEOUS:  # the app's finer categories, put together
                matching = [(o, ob) for o, ob in pairs if category(o) == MISCELLANEOUS]
                found = (len({id(o) for o in (objects if objects is not None else [o for o, _ in matching])
                              if category(o) == MISCELLANEOUS}), len(matching))
            else:
                found = (stats[name]["objects"], stats[name]["observations"])
            wanted = table[name].get(key, (0, 0))
            if found != wanted:
                differences.append((key, name, found, wanted))
    tiles = result.statistics["visual_observations"] + result.statistics["photographic_observations"]
    if tiles != sum(table[name][TOTAL][1] for name in CATEGORY_NAMES):
        differences.append((TOTAL, "observations tile", tiles, sum(table[n][TOTAL][1] for n in CATEGORY_NAMES)))
    return differences, {name: table[name] for name in CATEGORY_NAMES}
