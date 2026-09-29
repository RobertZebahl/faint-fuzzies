"""The app's one shared, in-memory copy of the data directory. Single-user, so one state for every
client; Reload re-reads everything from disk and every open page picks that up."""
from pathlib import Path

from faint_fuzzies.datadir import orbits_file, read_optic_names
from faint_fuzzies.domain import dss
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.orbits import parse_orbits
from faint_fuzzies.loading import (
    LoadedData,
    ProgressCallback,
    StaticCatalogues,
    load_data_dir,
    load_static_catalogues,
    scaled_progress,
)
from faint_fuzzies.media_pool import (
    OrbitSolution,
    build_dss_tasks,
    build_orbit_tasks,
    dss_key,
    matched_orbits,
    orbit_cache_path,
)
from faint_fuzzies.site.server import SiteServer
from faint_fuzzies.tasks import TaskPool

# how much of the initial-load progress bar goes to the (slow) static catalogues versus the (fast)
# rest; a Reload only redoes the rest, and so reports across the full 0..1 range on its own
STATIC_SHARE = 0.9


class AppState:
    """The app's one shared, in-memory copy of the data directory: the loaded catalogues, the DSS/orbit
    media task pool, and the Site page's preview server.

    :param data_dir: the data directory to load
    :param on_progress: reports the progress of the initial load
    :param fetch_dss: False leaves the DSS images to what is already in the data directory: none is queued
        or fetched
    :param generate_orbits: False leaves the orbit diagrams to what is already in the data directory: none
        is queued or drawn
    """

    def __init__(self, data_dir: Path, on_progress: ProgressCallback | None = None, fetch_dss: bool = True,
                 generate_orbits: bool = True):
        self.data_dir = data_dir
        self.fetch_dss = fetch_dss
        self.generate_orbits = generate_orbits
        self.task_pool = TaskPool()
        self._static: StaticCatalogues = load_static_catalogues(
            data_dir, scaled_progress(on_progress, 0.0, STATIC_SHARE))
        self.data: LoadedData = load_data_dir(
            data_dir, self._static, scaled_progress(on_progress, STATIC_SHARE, 1.0))
        self.optic_names: dict[str, str] = _load_optic_names(data_dir)
        self.orbit_elements: dict[int, list[OrbitSolution]] = {}
        self.site_server = SiteServer()  # the Site page's local PHP preview server, started on the first build
        self._refresh_media_tasks()
        self.task_pool.start()

    def reload(self, on_progress: ProgressCallback | None = None) -> None:
        """Re-reads the data directory (catalogues, sessions, observers, optic names) and re-seeds the
        media task pool from the fresh data. The static catalogues (see loading.StaticCatalogues) are not
        re-read, since they never change while the app runs.

        :param on_progress: reports the progress of the reload
        """
        self.data = load_data_dir(self.data_dir, self._static, on_progress)
        self.optic_names = _load_optic_names(self.data_dir)
        self._refresh_media_tasks()

    def _refresh_media_tasks(self) -> None:
        """Seeds the DSS/orbit task queue with whatever is currently missing on disk, and (re)computes
        which WDS pairs have orbital elements at all - the one piece of DSS/orbit status genuinely safe
        to cache per Reload, since it depends only on catalogue data. Everything else (does a file exist
        yet, is a task still queued) is deliberately never cached here: see media_pool.py for why - the
        background worker keeps finishing or failing tasks after this runs, so a cached status would go
        stale. id(Object) keys are only valid until the next reload, which replaces every Object.
        """
        collection = self.data.collection
        self.orbit_elements = matched_orbits(collection, _load_orbits(self.data_dir))
        dss_tasks = build_dss_tasks(self.data_dir, collection) if self.fetch_dss else []
        orbit_tasks = build_orbit_tasks(self.data_dir, self.orbit_elements) if self.generate_orbits else []
        self.task_pool.reset(dss_tasks + orbit_tasks)

    def build_site(self, output_dir: Path, on_progress: ProgressCallback | None = None,
                   prune: bool = False) -> dict:
        """Builds the website into `output_dir` from the data already loaded here - no independent reload from
        disk, so it always matches what Browse and Statistics currently show. Always symlinks its images; see
        site/output.write_site for `prune`. The caller (the Site page) is responsible for deciding whether to
        wait for the background task pool first - this only ever builds from what is on disk right now.

        :param output_dir: the directory to write the website into
        :param on_progress: reports the progress of the build
        :param prune: whether to delete, after writing, anything under `output_dir` this build does not
            account for; see site/output.write_site
        :returns: the build's report; see site/output.write_site
        """
        from faint_fuzzies.site.build import GlobalPages
        from faint_fuzzies.site.output import write_site
        pages = GlobalPages(self.data_dir, static=self._static, data=self.data, optic_names=self.optic_names)
        return write_site(pages, output_dir, prune=prune, on_progress=on_progress)

    def bump(self, obj: Object) -> None:
        """Moves this Object's DSS/orbit tasks (if either is still queued) to the front of the pool.

        :param obj: the Object whose tasks to bump
        """
        keys = set()
        task = dss.dss_task(obj)
        if task is not None:
            keys.add(dss_key(self.data_dir, task))
        for solution in self.orbit_elements.get(id(obj), []):
            keys.add(str(orbit_cache_path(self.data_dir, solution)))
        if keys:
            self.task_pool.bump(keys)


def _load_orbits(data_dir: Path) -> list:
    """orbits.txt (see datadir.orbits_file), optional like optic_names.json: a missing or unreadable
    file just means no orbit diagrams.

    :param data_dir: the data directory to look in
    :returns: the parsed orbital elements, or [] when there is no usable file
    """
    path = orbits_file(data_dir)
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return parse_orbits(text)


def _load_optic_names(data_dir: Path) -> dict[str, str]:
    """An optional optic code -> readable name mapping (for example "N,200,1200" -> 8" f/6"), never
    required for the app to run; a missing, unreadable or malformed file just means no renaming.

    :param data_dir: the data directory to look in
    :returns: the optic code -> readable name mapping, or {} when there is no usable file
    """
    return read_optic_names(data_dir)[0]
