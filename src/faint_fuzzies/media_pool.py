"""Building the DSS-image and orbit-diagram work a data directory currently needs, and checking it live.

`build_dss_tasks`/`build_orbit_tasks` are for seeding a TaskPool (see tasks.py) at startup and after every
Reload - a one-off scan of what is currently missing. Everything else here is meant to be called live,
on demand (whether a file exists, and dss_key/is the matching task still queued): the pool keeps working
in the background between reloads, so any status computed once and cached would go stale as soon as the
next fetch or generation finishes - or fails, which must stop showing as "still queued" too. Not under
ui/: both the app and, eventually, a website generator, build their pool from this.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.domain import dss, orbits
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.model import Object, ObjectAttribute
from faint_fuzzies.domain.names import component_name
from faint_fuzzies.tasks import MediaTask

DSS_DIR = "dss"
ORBITS_DIR = "orbits"
SITE_BUILD_DIR = "site-build"  # the app's own built website - generated and disposable, like DSS_DIR/ORBITS_DIR
DSS_CATEGORY = "dss"
ORBIT_CATEGORY = "orbit"


def dss_cache_dir(data_dir: Path, catalogue: str) -> Path:
    return data_dir / DSS_DIR / Path(catalogue).stem.casefold()


def site_build_dir(data_dir: Path) -> Path:
    return data_dir / SITE_BUILD_DIR


def dss_image_path(data_dir: Path, task: dss.DSSTask) -> tuple[Path, dss.DSSSource] | None:
    """The cache file of whichever source (and, for a by-name task, whichever position method) already
    succeeded, paired with that source, or None when none has been fetched yet - always checked live against
    disk, never cached: the background worker can finish a fetch at any time. Checked in the same order
    _dss_run fetches in, so this matches whichever file a fetch actually produced."""
    directory = dss_cache_dir(data_dir, task.catalogue)
    if task.by_name:
        for source in task.sources:
            path = directory / dss.cache_filename_by_name(source, task.label, task.fov)
            if path.is_file():
                return path, source
    for source in task.sources:
        path = directory / dss.cache_filename(source, task.position, task.fov)
        if path.is_file():
            return path, source
    return None


def unused_dss_images(data_dir: Path, collection: Collection) -> list[Path]:
    """Every .jpg under dss/ that no Object of the collection would fetch or read any more: a renamed or
    removed Object, changed coordinates, field of view or survey, a catalogue that is no longer present,
    or a file from an older naming scheme. A file for any of an Object's candidate surveys counts as used,
    since which one succeeded is only known by which file exists - and, for a by-name task, both its
    by-name and its coordinate candidates count, since either may be the one a fetch produced. A used
    file's thumbnail (see dss.thumbnail_path) counts as used too, whether or not it has been made yet.

    :param data_dir: the data directory
    :param collection: the collection whose Objects' DSS images stay in use
    :returns: the unused files, sorted
    """
    used: set[Path] = set()
    for obj in collection.objects:
        task = dss.dss_task(obj)
        if task is None:
            continue
        directory = dss_cache_dir(data_dir, task.catalogue)
        if task.by_name:
            used.update(directory / dss.cache_filename_by_name(source, task.label, task.fov) for source in task.sources)
        used.update(directory / dss.cache_filename(source, task.position, task.fov) for source in task.sources)
    used |= {dss.thumbnail_path(path) for path in used}
    root = data_dir / DSS_DIR
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.jpg") if path.is_file() and path not in used)


def remove_unused_dss_images(data_dir: Path, collection: Collection, dry_run: bool = False) -> list[Path]:
    """Deletes what unused_dss_images finds, then the catalogue folders that are left empty; returns the
    files found (deleted, unless dry_run). Only .jpg files are touched.

    :param data_dir: the data directory
    :param collection: the collection whose Objects' DSS images stay in use
    :param dry_run: whether to only report what would be deleted, without deleting
    :returns: the files found
    """
    unused = unused_dss_images(data_dir, collection)
    if dry_run:
        return unused
    for path in unused:
        path.unlink()
    root = data_dir / DSS_DIR
    for directory in sorted((d for d in root.rglob("*") if d.is_dir()), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return unused


def unused_orbit_images(data_dir: Path, collection: Collection,
                        orbital_elements: list[orbits.OrbitalElements]) -> list[Path]:
    """Every .jpg under orbits/ that no pair would plot any more: a solution that is gone from orbits.txt,
    a pair that is no longer in the WDS, a solution that gained or lost a sibling and so a number, or a file
    from an older naming scheme.

    :param data_dir: the data directory
    :param collection: the collection whose pairs' orbit diagrams stay in use
    :param orbital_elements: the parsed orbits.txt
    :returns: the unused files, sorted
    """
    used = {orbit_cache_path(data_dir, solution)
            for solutions in matched_orbits(collection, orbital_elements).values() for solution in solutions}
    root = data_dir / ORBITS_DIR
    if not root.is_dir():
        return []
    return sorted(path for path in root.glob("*.jpg") if path.is_file() and path not in used)


def remove_unused_orbit_images(data_dir: Path, collection: Collection,
                               orbital_elements: list[orbits.OrbitalElements], dry_run: bool = False) -> list[Path]:
    """Deletes what unused_orbit_images finds; returns the files found (deleted, unless dry_run). Only .jpg
    files are touched, and the orbits/ folder itself stays.

    :param data_dir: the data directory
    :param collection: the collection whose pairs' orbit diagrams stay in use
    :param orbital_elements: the parsed orbits.txt
    :param dry_run: whether to only report what would be deleted, without deleting
    :returns: the files found
    """
    unused = unused_orbit_images(data_dir, collection, orbital_elements)
    if not dry_run:
        for path in unused:
            path.unlink()
    return unused


def remove_all_orbit_images(data_dir: Path, dry_run: bool = False) -> list[Path]:
    """Deletes every .jpg under orbits/, the ones still in use too, so that all diagrams are drawn again (they
    show the years from the one they were drawn in); returns the files found (deleted, unless dry_run). Other
    files and the orbits/ folder stay.

    :param data_dir: the data directory
    :param dry_run: whether to only report what would be deleted, without deleting
    :returns: the files found
    """
    root = data_dir / ORBITS_DIR
    found = sorted(path for path in root.glob("*.jpg") if path.is_file()) if root.is_dir() else []
    if not dry_run:
        for path in found:
            path.unlink()
    return found


def dss_key(data_dir: Path, task: dss.DSSTask) -> str:
    """The TaskPool key this task is (or would be) queued under - always the first thing a fetch would try
    (its first source, by name first for a by-name task), even though a retry may end up succeeding under a
    different one; only used to ask the pool "is this still queued", never to look up the actual result (use
    dss_image_path for that).

    :param data_dir: the data directory
    :param task: the DSS task
    :returns: the key
    """
    directory = dss_cache_dir(data_dir, task.catalogue)
    if task.by_name:
        return str(directory / dss.cache_filename_by_name(task.sources[0], task.label, task.fov))
    return str(directory / dss.cache_filename(task.sources[0], task.position, task.fov))


@dataclass(frozen=True)
class OrbitSolution:
    """One plottable solution of a pair's orbit. `number` is its 1-based place among the pair's plottable
    solutions, in file order, and None when the pair has just one of them: a solution that cannot be
    plotted is not counted.

    :ivar elements: the orbital elements
    :ivar number: the solution's 1-based place among the pair's plottable solutions, None when it is the
        only one
    :ivar stem: the file name without .jpg (see orbit_stem)
    :ivar title: what the diagram says at the top (see orbit_title)
    """
    elements: orbits.OrbitalElements
    number: int | None
    stem: str
    title: str


def orbit_stem(name: str, component: str, number: int | None) -> str:
    """`<first name>[-<component>]-orbit[-solution-<n>]`, so that an existing orbit-image file keeps matching:
    the pair's first name with its spaces as hyphens, its component as its record writes it, and the number
    only when the pair has several solutions. Anything but letters, digits and hyphens becomes a hyphen
    (an asterisk is not allowed in a Windows file name).

    :param name: the pair's first name
    :param component: the pair's component, as its record writes it
    :param number: the solution's 1-based place among the pair's plottable solutions, None when it is the
        only one
    :returns: the file stem
    """
    safe = re.sub(r"[^A-Za-z0-9-]", "-", name.replace(" ", "-"))
    part = f"-{re.sub(r'[^A-Za-z0-9-]', '-', component)}" if component else ""
    return f"{safe}{part}-orbit{f'-solution-{number}' if number else ''}"


def orbit_title(pair: Object, number: int | None) -> str:
    """`<names, without the WDS id> [<component>] - Solution <n>`: every name of the pair, its component in
    brackets when it has one, the number only when the pair has several.

    :param pair: the pair the orbit belongs to
    :param number: the solution's 1-based place among the pair's plottable solutions, None when it is the
        only one
    :returns: the title
    """
    names = [n.strip() for n in str(pair.record.get(ObjectAttribute.NAME, "")).split(",") if n.strip()]
    if names and names[-1].startswith("WDS"):
        names.pop()
    component = component_name(pair)
    return (", ".join(names or [pair.label]) + (f" [{component}]" if component else "")
            + (f" - Solution {number}" if number else ""))


def orbit_cache_path(data_dir: Path, solution: OrbitSolution) -> Path:
    return data_dir / ORBITS_DIR / f"{solution.stem}.jpg"


def matched_orbits(collection: Collection, orbital_elements: list[orbits.OrbitalElements]
                   ) -> dict[int, list[OrbitSolution]]:
    """id(Object) -> its plottable solutions, in file order, for matched WDS pairs only. Safe to compute
    once per Reload and reuse (unlike dss_image_path/is_pending): which elements match which pair depends
    only on catalogue data, not on anything the background worker does.

    :param collection: the collection to match pairs against
    :param orbital_elements: the parsed orbits.txt
    :returns: id(pair Object) -> its plottable solutions
    """
    result: dict[int, list[OrbitSolution]] = {}
    matches = orbits.match_pairs(collection, orbital_elements)
    pairs = {id(o): o for o in collection.objects if id(o) in matches}
    for object_id, entries in matches.items():
        plottable = [elements for elements in entries if orbits.can_plot(elements)]
        several = len(plottable) > 1
        if plottable:
            pair = pairs[object_id]
            result[object_id] = [
                OrbitSolution(elements, number if several else None,
                              orbit_stem(pair.names[0], component_name(pair), number if several else None),
                              orbit_title(pair, number if several else None))
                for number, elements in enumerate(plottable, start=1)]
    return result


def build_dss_tasks(data_dir: Path, collection: Collection) -> list[MediaTask]:
    """One task per DSS-eligible Object whose cache file is currently missing.

    :param data_dir: the data directory
    :param collection: the collection to build tasks for
    :returns: the tasks
    """
    tasks: list[MediaTask] = []
    for obj in collection.objects:
        task = dss.dss_task(obj)
        if task is None or dss_image_path(data_dir, task) is not None:
            continue
        directory = dss_cache_dir(data_dir, task.catalogue)
        tasks.append(MediaTask(dss_key(data_dir, task), DSS_CATEGORY, _dss_run(task, directory),
                               f"{task.label} ({task.catalogue})",
                               "no DSS image could be fetched (a network problem, or the field is empty)"))
    return tasks


def _dss_run(task: dss.DSSTask, directory: Path):
    """The MediaTask.run callable for a DSS fetch: tries every source by name first (if `task.by_name`),
    then every source by coordinates, stopping at the first success.

    :param task: the fetch to run
    :param directory: the cache directory to write into
    :returns: a callable that runs the fetch and reports whether it succeeded
    """
    def run() -> bool:
        if task.by_name:
            for source in task.sources:
                destination = directory / dss.cache_filename_by_name(source, task.label, task.fov)
                if dss.fetch_dss_image_by_name(task.label, source, task.fov, destination):
                    return True
            # every source failed by name (unresolvable, no data, or a network problem); only now fall back
            # to the object's own coordinates - per-catalogue, not per-source, so a well-centered by-name
            # image from a less-preferred survey is never passed over for a miscentered by-coordinates one
            # from a more-preferred survey (see the fetch-DSS-by-name design log)
        for source in task.sources:
            destination = directory / dss.cache_filename(source, task.position, task.fov)
            if dss.fetch_dss_image_by_coordinates(task.coordinates, source, task.fov, destination):
                return True
        return False
    return run


def build_orbit_tasks(data_dir: Path, matched: dict[int, list[OrbitSolution]]) -> list[MediaTask]:
    """One task per solution of a matched pair whose orbit diagram is currently missing. `matched` is
    matched_orbits's result, already filtered to plottable elements.

    :param data_dir: the data directory
    :param matched: matched_orbits's result
    :returns: the tasks
    """
    tasks: list[MediaTask] = []
    for solutions in matched.values():
        for solution in solutions:
            destination = orbit_cache_path(data_dir, solution)
            if destination.is_file():
                continue
            tasks.append(MediaTask(str(destination), ORBIT_CATEGORY,
                                   _orbit_run(solution.elements, solution.title, destination), solution.title,
                                   "the orbit diagram could not be drawn"))
    return tasks


def _orbit_run(elements: orbits.OrbitalElements, title: str, destination: Path):
    """The MediaTask.run callable for generating one orbit diagram.

    :param elements: the orbital elements to plot
    :param title: the diagram's title
    :param destination: the file to write
    :returns: a callable that draws the diagram and reports whether it succeeded
    """
    def run() -> bool:
        return orbits.generate_orbit_diagram(elements, title, destination)
    return run
