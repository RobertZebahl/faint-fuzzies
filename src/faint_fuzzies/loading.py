"""Loading everything a data directory holds, for callers that only ever work with a data directory
(unlike the command line, which also accepts catalogues, sessions and observers given file by file)."""
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.checks import load_findings
from faint_fuzzies.datadir import discover
from faint_fuzzies.domain.catalogue import Catalogue, load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.observer import Observers, load_observers
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.session import Sessions, load_sessions
from faint_fuzzies.finding_index import FindingIndex
from faint_fuzzies.importers.attach import CommunityResult, attach_community

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

    :ivar catalogues: the other catalogues, not the own one
    """
    catalogues: list[Catalogue]


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
    return StaticCatalogues(catalogues)


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

    report("Loading the own catalogue", 0.15)
    own = load_catalogue(found.catalogues[0], sessions)

    # the other catalogues' objects are reused as-is; only their attached community observations may
    # have changed since the last reload, so those are cleared and reattached below
    for catalogue in static.catalogues:
        for obj in catalogue.objects:
            obj.community_observations = []

    # building the name index is the dominant cost of a reload (measured: ~1s of ~1.1s for 171k real
    # WDS objects) - report its own progress across this step's 0.15..0.6 share, rather than leaving the
    # whole thing as one silent gap between "Loading the own catalogue" and "Loading the observers"
    def index_progress(done: int, total: int) -> None:
        report("Building the name index", 0.15 + 0.45 * done / total if total else 0.6)

    collection = Collection([own, *static.catalogues], index_progress)

    report("Loading the observers", 0.6)
    observers = load_observers(found.observers) if found.observers else None

    report("Attaching community observations", 0.7)
    community = attach_community(collection, observers, found.sources) if found.sources else None

    references = References(collection)
    report("Checking the data", 0.85)
    found_findings = [*(sessions.findings if sessions else ()), *(observers.findings if observers else ()),
                      *(community.findings if community else ()),
                      *load_findings(root, collection, references)]
    findings = FindingIndex(collection.catalogues, found_findings, community.on_objects if community else (),
                            community.targets if community else None)
    report("Done", 1.0)
    return LoadedData(collection, references, sessions, observers, community, findings)


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
