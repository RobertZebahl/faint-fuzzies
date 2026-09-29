"""The Statistics page: one section for the owner's private log (sessions, locations, optics, seen
status), then the same per-project and per-sublist counts `list` already computes for the website
(objects, visual/photographic observations, sketches, photographs, observers). Filtered/ad hoc
statistics for the current Objects browse selection are a later addition."""
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from nicegui import ui

from faint_fuzzies.domain.lists import (
    LISTS,
    OBJECT_TYPE_SUBLISTS,
    ListResult,
    build_list,
    counted_observations,
    is_uncategorized,
    sublist_sort_key,
    sublist_title,
)
from faint_fuzzies.domain.model import Object, ObjectType
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.domain.observer import OWN_ID, Observers
from faint_fuzzies.domain.seen import SeenStatus, is_observation_seen, seen_status
from faint_fuzzies.ui.nav import header
from faint_fuzzies.ui.state import AppState

SUBLIST_COLUMNS = [
    {"name": "sublist", "label": "Sublist", "field": "sublist", "align": "left", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "visual", "label": "Visual", "field": "visual", "sortable": True},
    {"name": "photographic", "label": "Photographic", "field": "photographic", "sortable": True},
    {"name": "sketches", "label": "Sketches", "field": "sketches", "sortable": True},
    {"name": "photographs", "label": "Photographs", "field": "photographs", "sortable": True},
]
# Deep Sky With Binoculars never has photographic contributions (neither of its formats has a
# photographic variant), so that column and "photographs" are dropped entirely, unlike Double Stars.
DEEP_SKY_SUBLIST_COLUMNS = [
    {"name": "sublist", "label": "Sublist", "field": "sublist", "align": "left", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "visual", "label": "Visual", "field": "visual", "sortable": True},
    {"name": "sketches", "label": "Sketches", "field": "sketches", "sortable": True},
]
# Global never has photographic contributions (no observer submits it a "photographic" method
# observation), so that column and "photographs" are always 0 there; "visual" is really just
# "observations" once that's the only method left. "Seen"/"Failed" only make sense where the rows are
# purely by Object type - see type_category_stats. "Failed" matches domain.seen.SeenStatus.FAILED:
# an Object with an observation here, but none of them a seen result.
GLOBAL_SUBLIST_COLUMNS = [
    {"name": "sublist", "label": "Object Type", "field": "sublist", "align": "left", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "seen", "label": "Seen", "field": "seen", "sortable": True},
    {"name": "failed", "label": "Failed", "field": "failed", "sortable": True},
    {"name": "observations", "label": "Observations", "field": "observations", "sortable": True},
    {"name": "sketches", "label": "Sketches", "field": "sketches", "sortable": True},
]
LOCATION_COLUMNS = [
    {"name": "location", "label": "Location", "field": "location", "align": "left", "sortable": True},
    {"name": "sessions", "label": "Sessions", "field": "sessions", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "observations", "label": "Observations", "field": "observations", "sortable": True},
]
OPTIC_COLUMNS = [
    {"name": "optic", "label": "Optic", "field": "optic", "align": "left", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "observations", "label": "Observations", "field": "observations", "sortable": True},
]
OBSERVER_COLUMNS = [
    {"name": "observer", "label": "Observer", "field": "observer", "align": "left", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "sortable": True},
    {"name": "observations", "label": "Observations", "field": "observations", "sortable": True},
]
ROWS_PER_PAGE = 10  # default page size for the longer lists on this page (locations, optics, observers)


def build(state: AppState) -> None:
    """Builds the Statistics page.

    :param state: the app's shared state
    """
    StatisticsPage(state)


@contextmanager
def _section(title: str, *, expanded: bool = False) -> Iterator[None]:
    """A collapsible section of the page, titled and indented like the others.

    :param title: the section's title
    :param expanded: whether the section starts open
    """
    with (
        ui.expansion(title, value=expanded).classes("w-full")
        .props('header-class="text-h6" expand-icon-class="text-h6"'),
        ui.column().classes("w-full gap-2 q-px-md q-pb-md"),
    ):
        yield


class StatisticsPage:
    """The Statistics page's controller: the private-log section, then one section per project/Global list.

    :param state: the app's shared state
    """

    def __init__(self, state: AppState):
        self.state = state
        header("statistics", state, self._render)
        self.body = ui.column().classes("w-full max-w-full p-4 gap-6")
        self._render()

    def _render(self) -> None:
        """(Re)builds every section of the page from the current state; called on load and after a Reload."""
        self.body.clear()
        with self.body:
            with _section("Private Observations", expanded=True):
                self._private_section()
            for name, definition in LISTS.items():
                result = build_list(definition, self.state.data.collection, self.state.data.references,
                                    self.state.data.observers)
                self._list_section(name, result)

    def _private_section(self) -> None:
        """Builds the "Private Observations" section: the owner's own log, by location, by optic and by
        Object type."""
        collection = self.state.data.collection
        sessions = self.state.data.sessions
        own_objects = [obj for obj in collection.objects if obj.rank == 0]
        seen_counts = Counter(seen_status(obj) for obj in own_objects)
        private_observations = [(obj, o) for obj in own_objects for o in obj.observations if not o.public]

        location_counts: dict[str, int] = {}
        for session in sessions.sessions if sessions else ():
            location_counts[session.location.name] = location_counts.get(session.location.name, 0) + 1

        location_observations: dict[str, int] = {}
        location_objects: dict[str, set[int]] = {}
        optic_counts: dict[str, int] = {}
        optic_objects: dict[str, set[int]] = {}
        for obj, observation in private_observations:
            if observation.session:
                location = observation.session.location.name
                location_observations[location] = location_observations.get(location, 0) + 1
                location_objects.setdefault(location, set()).add(id(obj))
            if observation.optic:
                code = observation.optic.code
                optic_counts[code] = optic_counts.get(code, 0) + 1
                optic_objects.setdefault(code, set()).add(id(obj))

        with ui.row().classes("gap-8 q-my-sm"):
            _stat_tile("Sessions", len(sessions.sessions) if sessions else 0)
            if sessions and sessions.sessions:
                _stat_tile("First session", sessions.sessions[0].start.date().isoformat())
                _stat_tile("Latest session", sessions.sessions[-1].start.date().isoformat())
            _stat_tile("Locations", len(location_counts))
            _stat_tile("Optics used", len(optic_counts))
        with ui.row().classes("gap-8 q-my-sm"):
            _stat_tile("Objects", seen_counts[SeenStatus.SEEN] + seen_counts[SeenStatus.FAILED])
            _stat_tile("Seen", seen_counts[SeenStatus.SEEN])
            _stat_tile("Failed", seen_counts[SeenStatus.FAILED])
            _stat_tile("Observations", len(private_observations))
            _stat_tile("Sketches", sum(_sketch_file_count(o) for _, o in private_observations))

        if location_counts:
            ui.label("Sessions per location").classes("text-subtitle2 q-mt-md")
            rows = [{"location": name, "sessions": count,
                     "observations": location_observations.get(name, 0),
                     "objects": len(location_objects.get(name, ()))}
                    for name, count in sorted(location_counts.items(), key=lambda kv: -kv[1])]
            ui.table(columns=LOCATION_COLUMNS, rows=rows, row_key="location", pagination=ROWS_PER_PAGE) \
                .classes("w-full").props("dense")

        if optic_counts:
            ui.label("Optics used").classes("text-subtitle2 q-mt-md")
            rows = [{"optic": self.state.optic_names.get(code, code), "observations": count,
                     "objects": len(optic_objects.get(code, ()))}
                    for code, count in sorted(optic_counts.items(), key=lambda kv: -kv[1])]
            ui.table(columns=OPTIC_COLUMNS, rows=rows, row_key="optic", pagination=ROWS_PER_PAGE) \
                .classes("w-full").props("dense")

        if private_observations:
            ui.label("By Object Type").classes("text-subtitle2 q-mt-md")
            stats_by_name = type_category_stats(private_observations)
            rows = [{"sublist": sublist_title(name), **stats_by_name[name]}
                    for name in sorted(stats_by_name, key=sublist_sort_key)]
            ui.table(columns=GLOBAL_SUBLIST_COLUMNS, rows=rows, row_key="sublist", pagination=0) \
                .classes("w-full").props("dense")

    def _list_section(self, name: str, result: ListResult) -> None:
        """Builds one project/Global list's section: its totals, its sublists (or, for Global, its By Object
        Type table), its observers, and, for Global, one sub-section per observer.

        :param name: the list's name, a key of domain.lists.LISTS
        :param result: the list, already built
        """
        is_global = name == "global"
        is_deep_sky_binoculars = name == "project-deep-sky-with-binoculars"
        all_pairs = get_all_observation_pairs(result) if is_global else None
        with _section(_section_title(name)):
            with ui.row().classes("gap-8 q-my-sm"):
                _stat_tile("Objects", result.statistics["objects"])
                if is_global:
                    assert all_pairs is not None  # set above, together with is_global
                    seen, failed = _seen_counts(all_pairs)
                    _stat_tile("Seen", seen)
                    _stat_tile("Failed", failed)
                    # Global never has photographic contributions, so "visual" is just "observations"
                    _stat_tile("Observations", result.statistics["visual_observations"])
                else:
                    _stat_tile("Visual observations", result.statistics["visual_observations"])
                    if not is_deep_sky_binoculars:
                        _stat_tile("Photographic observations", result.statistics["photographic_observations"])
                _stat_tile("Sketches", result.statistics["sketches"])
                if not is_global and not is_deep_sky_binoculars:
                    _stat_tile("Photographs", result.statistics["photographs"])
                _stat_tile("Observers", len(result.statistics["observers"]))

            # Global's sublists are purely by Object type - "By Object Type" here means all observations
            # of every Global contributor combined (see get_all_observation_pairs), unlike the per-observer sections
            # below. The two projects also have rating-, tag- and position-based sublists (best-of,
            # colored, the right ascension bands, ...), so they keep the more general "Sublists" label.
            if is_global:
                assert all_pairs is not None  # set above, together with is_global
                ui.label("By Object Type").classes("text-subtitle2 q-mt-md")
                stats_by_name = type_category_stats(all_pairs, [entry.unit for entry in result.entries])
                rows = [{"sublist": sublist_title(sublist_name), **stats_by_name[sublist_name]}
                        for sublist_name in sorted(stats_by_name, key=sublist_sort_key)]
                columns = GLOBAL_SUBLIST_COLUMNS
            else:
                ui.label("Sublists").classes("text-subtitle2 q-mt-md")
                names = [n for n in result.sublist_statistics if n != "complete"]  # "complete" is above
                rows = [_sublist_row(sublist_name, result.sublist_statistics[sublist_name]) for sublist_name in names]
                columns = DEEP_SKY_SUBLIST_COLUMNS if is_deep_sky_binoculars else SUBLIST_COLUMNS
            ui.table(columns=columns, rows=rows, row_key="sublist", pagination=0) \
                .classes("w-full").props("dense")

            observer_stats = _observer_stats(result, self.state.data.observers)
            if observer_stats:
                ui.label("Observers").classes("text-subtitle2 q-mt-md")
                rows = [{"observer": name, "objects": stats["objects"], "observations": stats["observations"]}
                        for name, stats in sorted(observer_stats.items(), key=lambda kv: -kv[1]["observations"])]
                ui.table(columns=OBSERVER_COLUMNS, rows=rows, row_key="observer", pagination=ROWS_PER_PAGE) \
                    .classes("w-full").props("dense")

        if is_global:
            observers = self.state.data.observers
            for observer in _owner_first(result.statistics["observers"], observers):
                with _section(f"Global - {observer['name']}"):
                    self._global_observer_section(result, observer["id"], observers)

    def _global_observer_section(self, result: ListResult, observer_id: str, observers: Observers | None) -> None:
        """A copy of the Global section limited to one observer's own contributions - same object-type
        categories, but no Observers table (it would just be this one observer).

        :param result: the Global list, already built
        :param observer_id: the observer to show
        :param observers: the observers, for resolving the owner's id
        """
        pairs = get_observer_pairs(result, observer_id, observers)
        totals = _pair_totals(pairs)
        seen, failed = _seen_counts(pairs)
        with ui.row().classes("gap-8 q-my-sm"):
            _stat_tile("Objects", totals["objects"])
            _stat_tile("Seen", seen)
            _stat_tile("Failed", failed)
            _stat_tile("Observations", totals["observations"])
            _stat_tile("Sketches", totals["sketches"])

        ui.label("By Object Type").classes("text-subtitle2 q-mt-md")
        stats_by_name = type_category_stats(pairs)
        rows = [{"sublist": sublist_title(name), **stats_by_name[name]}
                for name in sorted(stats_by_name, key=sublist_sort_key)]
        ui.table(columns=GLOBAL_SUBLIST_COLUMNS, rows=rows, row_key="sublist", pagination=0) \
            .classes("w-full").props("dense")


_LIST_TITLE_OVERRIDES = {
    "project-double-stars": "Double Stars",
    "project-deep-sky-with-binoculars": "Deep Sky With Binoculars",
}  # strips the "project-" prefix and, for the latter, fixes sublist_title()'s "With" capitalisation


def _section_title(name: str) -> str:
    """"Global" is the site-wide list, not a Project (CONTEXT.md reserves that word for Double Stars
    and Deep Sky With Binoculars), so only those two get the "Project - " prefix.

    :param name: the list's name, a key of domain.lists.LISTS
    :returns: the section's title
    """
    title = _LIST_TITLE_OVERRIDES.get(name, sublist_title(name))
    return title if name == "global" else f"Project - {title}"


def _stat_tile(label: str, value: int | str) -> None:
    """A single labeled number or short text, as used throughout this page's summary rows.

    :param label: the tile's caption
    :param value: the value to show; an int is thousands-separated
    """
    text = f"{value:,}" if isinstance(value, int) else str(value)
    with ui.column().classes("items-start gap-0"):
        ui.label(text).classes("text-h5 text-weight-medium")
        ui.label(label).classes("text-caption text-grey-7")


def _observer_stats(result: ListResult, observers: Observers | None) -> dict[str, dict[str, int]]:
    """Per observer: how many objects (entries) they contributed to, and how many observations that
    took in total (an observer can have several observations of the same object). The owner's own (an
    observation with none) resolves to their real name, the same as the "Observers" count above it -
    "you" would otherwise show up as a second, uncounted entry for the same person.

    :param result: the list to summarize
    :param observers: the observers, for resolving the owner's name
    :returns: observer name -> {"observations": count, "objects": count}
    """
    owner = observers.owner if observers else None
    observation_counts: dict[str, int] = {}
    object_ids: dict[str, set[int]] = {}
    for entry in result.entries:
        contributors: set[str] = set()
        for found in counted_observations(entry):
            observer = found.observation.observer
            name = observer.name if observer else (owner.name if owner else "you")
            observation_counts[name] = observation_counts.get(name, 0) + 1
            contributors.add(name)
        for name in contributors:
            object_ids.setdefault(name, set()).add(id(entry))
    return {name: {"observations": count, "objects": len(object_ids[name])}
            for name, count in observation_counts.items()}


def _sublist_row(name: str, stats: dict[str, Any]) -> dict:
    return {
        "sublist": sublist_title(name),
        "objects": stats["objects"],
        "visual": stats["visual_observations"],
        "photographic": stats["photographic_observations"],
        "sketches": stats["sketches"],
        "photographs": stats["photographs"],
    }


def _sketch_file_count(observation: Observation) -> int:
    return len(observation.sketches)


def _seen_counts(pairs: list[tuple[Object, Observation]]) -> tuple[int, int]:
    """Among the distinct Objects in pairs, how many were seen at least once and how many had an
    observation but never a seen one - "failed", the same term domain.seen.SeenStatus.FAILED uses for
    this. An Object counts as seen if any of ITS observations here reports a seen result. Every Object
    here has at least one matching observation by construction, so the two counts add up to all of them;
    SeenStatus.NOT_OBSERVED doesn't apply here, unlike the private log's own Seen/Failed tiles, since an
    Object with no observation in `pairs` was never in `pairs` to begin with.

    :param pairs: the (Object, Observation) pairs to count
    :returns: (seen count, failed count)
    """
    best: dict[int, bool] = {}
    for obj, observation in pairs:
        double_star = ObjectType.DOUBLE_STAR in obj.types
        key = id(obj)
        best[key] = best.get(key, False) or is_observation_seen(observation, double_star)
    seen = sum(1 for was_seen in best.values() if was_seen)
    return seen, len(best) - seen


def type_category_stats(pairs: list[tuple[Object, Observation]],
                         objects: list[Object] | None = None) -> dict[str, dict[str, int]]:
    """The type categories OBJECT_TYPE_SUBLISTS defines (plus "others"), counted over an arbitrary set
    of (Object, Observation) pairs: objects counted once each, observations and sketch files summed, and
    split into seen/failed (see _seen_counts). Used for the private-only breakdown, the Global section's
    own By Object Type table (all observations, see get_all_observation_pairs) and a single observer's slice of
    it. `objects` are the Objects to count instead of those of the pairs: the Global list's total counts
    every Object of the list, also one that only has a Header and so no pair.

    :param pairs: the (Object, Observation) pairs to count
    :param objects: the Objects to count instead of those of `pairs`, when given
    :returns: category name -> {"objects", "observations", "sketches", "seen", "failed"}
    """
    categories = {**OBJECT_TYPE_SUBLISTS, "others": is_uncategorized}
    stats = {}
    for name, rule in categories.items():
        matching = [(obj, observation) for obj, observation in pairs if rule(obj)]
        seen, failed = _seen_counts(matching)
        stats[name] = {
            "objects": len({id(obj) for obj in objects if rule(obj)}) if objects is not None
            else len({id(obj) for obj, _ in matching}),
            "observations": len(matching),
            "sketches": sum(_sketch_file_count(observation) for _, observation in matching),
            "seen": seen,
            "failed": failed,
        }
    return stats


def _pair_totals(pairs: list[tuple[Object, Observation]]) -> dict[str, int]:
    """Objects, observations and sketch files of a set of (Object, Observation) pairs, undivided by
    category - a category's "objects" can't just be summed across categories for this, since an Object
    matching more than one category would be double-counted.

    :param pairs: the (Object, Observation) pairs to total
    :returns: {"objects", "observations", "sketches"}
    """
    return {
        "objects": len({id(obj) for obj, _ in pairs}),
        "observations": len(pairs),
        "sketches": sum(_sketch_file_count(observation) for _, observation in pairs),
    }


def _owner_first(observer_list: list[dict[str, str]], observers: Observers | None) -> list[dict[str, str]]:
    """result.statistics["observers"] sorted alphabetically by surname, with the owner moved to the
    front - their "Global - <name>" section leads, the Global observers follow in their existing order.

    :param observer_list: result.statistics["observers"]
    :param observers: the observers, for resolving the owner's id
    :returns: the reordered list
    """
    owner_id = observers.owner_id() if observers else OWN_ID
    owner = [o for o in observer_list if o["id"] == owner_id]
    others = [o for o in observer_list if o["id"] != owner_id]
    return owner + others


def get_observer_pairs(
    result: ListResult, observer_id: str, observers: Observers | None
) -> list[tuple[Object, Observation]]:
    """One observer's (canonical Object, Observation) pairs across every entry of a built list - the
    owner's own observations (format is None) when observer_id is the owner's id.

    :param result: the list to search
    :param observer_id: the observer whose pairs to collect
    :param observers: the observers, for resolving the owner's id
    :returns: the matching pairs
    """
    owner_id = observers.owner_id() if observers else OWN_ID
    pairs = []
    for entry in result.entries:
        for found in counted_observations(entry):
            observer = found.observation.observer
            this_id = observer.id if observer else owner_id
            if this_id == observer_id:
                pairs.append((entry.unit, found.observation))
    return pairs


def get_all_observation_pairs(result: ListResult) -> list[tuple[Object, Observation]]:
    """Every (canonical Object, Observation) pair across a built list's entries, regardless of observer -
    "all observations from everyone" for the Global section's own By Object Type table, as opposed to
    get_observer_pairs, which is one observer's slice of the same entries.

    :param result: the list to collect pairs from
    :returns: every pair
    """
    return [(entry.unit, found.observation) for entry in result.entries for found in counted_observations(entry)]
