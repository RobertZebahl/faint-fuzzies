"""Loading everything a data directory holds, for callers that only ever work with a data directory
(unlike the command line, which also accepts catalogues, sessions and observers given file by file)."""
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from faint_fuzzies.checks import load_findings
from faint_fuzzies.datadir import DataDir, discover, wds_alternative_names_file
from faint_fuzzies.domain.catalogue import Catalogue, load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.findings import ERROR, Finding
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.domain.observer import Observers, load_observers
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.session import Sessions, load_sessions
from faint_fuzzies.finding_index import FindingIndex
from faint_fuzzies.importers.attach import CommunityResult, attach_community, attach_owner_double_stars
from faint_fuzzies.importers.owner_double_stars import is_attach_record, read_owner_double_stars
from faint_fuzzies.importers.wds_alternative_names import apply_alternative_names, read_wds_alternative_names

# a snapshot of what loading.apply_wds_overlay may mutate on one WDS Object, so the mutation can be
# undone before it is reapplied fresh on the next reload (see StaticCatalogues.wds_snapshot)
_WdsSnapshot = tuple[tuple[str, ...], tuple[str, ...], tuple[Observation, ...], dict[str, Any]]

# A step description and how far along loading is (0 to 1); see load_data_dir. The web app turns this
# into a progress bar, the command line into a line of text - the loader itself knows nothing about
# either, so the same callback shape works for both, and for whatever later needs one (generating the
# website, fetching images, ...).
ProgressCallback = Callable[[str, float], None]


def step_reporter() -> ProgressCallback:
    """A ProgressCallback that prints each step to stderr once: some steps (e.g. building the name index)
    report many times in a row for one fine-grained progress bar, which a line of text has no use for."""
    last_step = None

    def report(step: str, _fraction: float) -> None:
        nonlocal last_step
        if step != last_step:
            print(f"faint-fuzzies: {step}...", file=sys.stderr)
            last_step = step
    return report


@dataclass(frozen=True)
class StaticCatalogues:
    """The other catalogues (catalogues/\\*.json, e.g. the WDS) of a data directory, parsed once. They
    are never modified while the app runs - only the own catalogue, the sessions and the community
    files are - so re-parsing them on every Reload is wasted work; the WDS alone is ~170k records,
    against ~7k for a typical own catalogue, so this is where nearly all loading time goes.

    The WDS's own Objects are, however, *mutated* every load: a double star Group or pair may carry
    Alternative names, and a non-DISABLE_WDS own-catalogue double-star record attaches its observations
    and tags directly onto its match (see CONTEXT.md, Own catalogue). Both can change between reloads
    (they are the user's own files), so `wds_snapshot` keeps each affected field as it was first parsed,
    to reset from before reapplying fresh on every load_data_dir call - the same idea as
    community_observations, just covering more fields.

    :ivar catalogues: the other catalogues, not the own one
    :ivar wds_snapshot: id(object) -> its pristine (names, groups, observations, record) for every object
        of the WDS catalogue, empty when no WDS catalogue was loaded
    """
    catalogues: list[Catalogue]
    wds_snapshot: dict[int, _WdsSnapshot] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedData:
    """Everything load_data_dir loads for one data directory.

    :ivar collection: every catalogue, the own one first
    :ivar references: the collection's cross-catalogue references
    :ivar sessions: the loaded sessions, if there are any
    :ivar observers: the loaded observers, if there are any
    :ivar community: the result of attaching the community files, if there were any
    :ivar findings: the finding index
    """
    collection: Collection
    references: References
    sessions: Sessions | None
    observers: Observers | None
    community: CommunityResult | None
    findings: FindingIndex


def load_static_catalogues(root: Path, on_progress: ProgressCallback | None = None) -> StaticCatalogues:
    """Parses the other catalogues of a data directory (not the own one). Load once per data directory
    and pass the result to every load_data_dir call for it; see StaticCatalogues.

    :param root: the data directory
    :param on_progress: reports progress through the load
    :returns: the parsed other catalogues
    """
    report = on_progress or (lambda step, fraction: None)

    report("Finding the files", 0.0)
    others = discover(root).catalogues[1:]  # [0] is the own catalogue; load_data_dir reloads that one

    catalogues = []
    total = len(others) or 1
    for index, path in enumerate(others):
        report(f"Loading {path.name}", index / total)
        catalogues.append(load_catalogue(path, check_values=False))  # converted: `validate` checks them
    report("Done", 1.0)

    wds = next((c for c in catalogues if Path(c.name).stem.casefold() == "wds"), None)
    snapshot = ({id(obj): (obj.names, obj.groups, obj.observations, dict(obj.record)) for obj in wds.objects}
               if wds is not None else {})
    return StaticCatalogues(catalogues, snapshot)


def load_data_dir(root: Path, static: StaticCatalogues, on_progress: ProgressCallback | None = None) -> LoadedData:
    """Loads the own catalogue, the sessions, the observers and the attached community observations of
    a data directory - the parts that can change while the app runs - and combines them with the
    already-parsed other catalogues in `static` (see load_static_catalogues). References are always
    recomputed: they depend on both the own and the other catalogues, so they can't be cached across a
    reload. on_progress is called at least once, with 1.0, when loading is done.

    :param root: the data directory
    :param static: the already-parsed other catalogues
    :param on_progress: reports progress through the load
    :returns: everything loaded
    """
    report = on_progress or (lambda step, fraction: None)

    report("Finding the files", 0.0)
    found = discover(root)

    report("Loading the sessions", 0.05)
    sessions = load_sessions(found.sessions) if found.sessions else None

    collection, double_star_findings, double_star_targets = build_double_star_collection(
        root, found, static, sessions, scaled_progress(report, 0.15, 0.6))

    report("Loading the observers", 0.6)
    observers = load_observers(found.observers) if found.observers else None

    report("Attaching community observations", 0.7)
    community = attach_community(collection, observers, found.sources) if found.sources else None

    references = References(collection)
    report("Checking the data", 0.85)
    found_findings = [*double_star_findings,
                      *(sessions.findings if sessions else ()), *(observers.findings if observers else ()),
                      *(community.findings if community else ()),
                      *load_findings(root, collection, references)]
    targets = {**double_star_targets, **(community.targets if community else {})}
    findings = FindingIndex(collection.catalogues, found_findings, community.on_objects if community else (),
                            targets)
    report("Done", 1.0)
    return LoadedData(collection, references, sessions, observers, community, findings)


def build_double_star_collection(root: Path, found: DataDir, static: StaticCatalogues, sessions: Sessions | None,
                                on_progress: ProgressCallback | None = None
                                ) -> tuple[Collection, list[Finding], dict[int, Object]]:
    """Builds the Collection of a data directory: the own catalogue (its double-star attach-records split
    out first, see importers.owner_double_stars) together with `static`'s already-parsed other catalogues,
    with the WDS's Alternative names and the own catalogue's double-star observations/tags applied fresh
    (see StaticCatalogues.wds_snapshot for why they must be reset first). Shared by load_data_dir and by
    any caller that builds its own Collection directly from a data directory instead (cli.py's --data-dir
    commands) rather than going through load_data_dir's own sessions/observers/community/references wiring.

    :param root: the data directory
    :param found: what discover(root) found
    :param static: the already-parsed other catalogues (see load_static_catalogues)
    :param sessions: the loaded sessions, if there are any, for the own catalogue's private observations
    :param on_progress: reports progress through the step (0 to 1); building the name index is its
        dominant cost (measured: ~1s of ~1.1s for 171k real WDS objects)
    :returns: the collection, the findings made attaching the own catalogue's double stars, and the Object
        each info/warning finding about a successful match is about, by id() (see
        importers.attach.match_any_name) - a double-star attach-record is not among its own catalogue's
        objects, so this is the only way to find one for a FindingIndex
    """
    report = on_progress or (lambda step, fraction: None)
    double_star_findings: list[Finding] = []
    double_star_targets: dict[int, Object] = {}

    report("Loading the own catalogue", 0.0)
    own_stars = read_owner_double_stars(found.catalogues[0], double_star_findings, sessions)
    own = load_catalogue(found.catalogues[0], sessions, skip=is_attach_record)

    # the other catalogues' objects are reused as-is; only their attached community observations, and a
    # double star's Alternative names and owner-attached observations/tags, may have changed since the
    # last reload (they are the user's own files) - so all of those are reset to how the catalogue was
    # first parsed, then reapplied fresh, below
    for catalogue in static.catalogues:
        for obj in catalogue.objects:
            obj.community_observations = []
            snapshot = static.wds_snapshot.get(id(obj))
            if snapshot is not None:
                obj.names, obj.groups, obj.observations, record = snapshot
                obj.record = dict(record)

    wds = next((c for c in static.catalogues if Path(c.name).stem.casefold() == "wds"), None)
    if wds is not None:
        names_path = wds_alternative_names_file(root)
        if names_path is not None:
            entries, name_findings = read_wds_alternative_names(names_path)
            double_star_findings.extend(name_findings)
            apply_alternative_names(wds.objects, entries, double_star_findings)

    def index_progress(done: int, total: int) -> None:
        report("Building the name index", 0.9 * done / total if total else 0.9)

    collection = Collection([own, *static.catalogues], index_progress)

    report("Attaching the own catalogue's double stars", 0.9)
    if wds is not None:
        attach_owner_double_stars(collection, own_stars, found.catalogues[0].name, double_star_findings,
                                  double_star_targets)
    elif own_stars:
        # never lose these silently: without the WDS loaded, nothing exists for them to attach to, so
        # their observations and tags would otherwise vanish from the collection with no sign why
        double_star_findings.append(Finding(
            found.catalogues[0].name, own_stars[0].number, own_stars[0].name, None, ERROR,
            f"{len(own_stars)} double star record(s) need the WDS catalogue to attach to "
            "(convert wds.txt and add it to catalogues/) - none are loaded until then"))
    report("Done", 1.0)
    return collection, double_star_findings, double_star_targets


def scaled_progress(callback: ProgressCallback | None, start: float, end: float) -> ProgressCallback:
    """Wraps a progress callback so its own 0..1 range is reported as start..end instead - for
    combining several loading phases (each reporting its own 0..1) into one overall progress bar.

    :param callback: the callback to wrap, or None
    :param start: the start of the range `callback`'s 0..1 is scaled into
    :param end: the end of the range `callback`'s 0..1 is scaled into
    :returns: the wrapped callback
    """
    def report(step: str, fraction: float) -> None:
        if callback is not None:
            callback(step, start + (end - start) * fraction)
    return report
