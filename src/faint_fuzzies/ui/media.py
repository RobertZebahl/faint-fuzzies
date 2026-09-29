"""Serving the Sketch, Photograph, Image, DSS image and Orbit diagram files an Object or
Observation refers to.

Only five subtrees of the data directory are ever served, mounted once when the app starts: the owner's
own media, the two community trees, and the dss/ and orbits/ caches. This is deliberately narrower than
serving the whole data directory, which would also expose objects.json, sessions.json and observers.json
(with its email addresses). Mounted directories are read from disk per request, so files (and whole new
observer subfolders) added after startup are served too, with no restart needed - but a directory that
does not exist yet at mount time can never be mounted (NiceGUI/Starlette require it to exist), so every
one of them is created if missing. Only their top level is created here, never a fake per-observer
subfolder or cache file - those only ever come from an actual submission, fetch or generation.
"""
from pathlib import Path

from nicegui import app

from faint_fuzzies.datadir import OBSERVATIONS, OWNER, OWNER_MEDIA_FOLDERS, community_media_folder
from faint_fuzzies.domain import dss as dss_domain
from faint_fuzzies.domain.model import Object, ObservationAttribute
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.media_pool import DSS_DIR, ORBITS_DIR, dss_image_path, dss_key, orbit_cache_path
from faint_fuzzies.site.media import SOURCE_LABELS
from faint_fuzzies.ui.state import AppState

_OWNER_PREFIX = "/media/owner"
_GLOBAL_PREFIX = "/media/global"
_PROJECTS_PREFIX = "/media/projects"
_DSS_PREFIX = "/media/dss"
_ORBITS_PREFIX = "/media/orbits"

_MEDIA_ATTRIBUTES = {ObservationAttribute.SKETCH: "sketches", ObservationAttribute.PHOTOGRAPH: "photographs",
                     ObservationAttribute.IMAGE: "images"}


def mount_static_media(data_dir: Path) -> None:
    """Mounts the media folders under this data directory, creating any of them that do not exist yet
    (top level only - never a fake per-observer subfolder or cache file). Call once per app run.

    :param data_dir: the data directory to serve media from
    """
    owner = data_dir / OWNER
    for folder in OWNER_MEDIA_FOLDERS.values():
        path = owner / folder
        path.mkdir(parents=True, exist_ok=True)
        app.add_static_files(f"{_OWNER_PREFIX}/{folder}", path)
    for prefix, name in ((_GLOBAL_PREFIX, "global"), (_PROJECTS_PREFIX, "projects")):
        path = data_dir / OBSERVATIONS / name
        path.mkdir(parents=True, exist_ok=True)
        app.add_static_files(prefix, path)
    for prefix, name in ((_DSS_PREFIX, DSS_DIR), (_ORBITS_PREFIX, ORBITS_DIR)):
        path = data_dir / name
        path.mkdir(parents=True, exist_ok=True)
        app.add_static_files(prefix, path)


def get_dss_status(state: AppState, obj: Object) -> tuple[str | None, str | None, bool, str]:
    """(the thumbnail's URL once it exists, the full-size image's URL once it exists, whether a fetch for it
    is queued or running, the label to show under it) - always checked live, never from a cached status,
    since the background worker can finish or fail a fetch at any time (see media_pool.py). The label names
    the survey that actually succeeded and the field of view, the same as the website's own DSS caption (see
    site/media.py); while nothing has been fetched yet, it just says "DSS image".

    The thumbnail is the same shared, 200x200 file the website builder also writes and reads (see
    domain.dss.thumbnail_path): made here on first request if missing or stale, next to the full-size image
    it is made from - a local file, so this is fast enough to do inline. If making it fails, the full-size
    image's own URL is returned instead, exactly as if no thumbnail-sharing existed.

    :param state: the app's shared state
    :param obj: the Object to check
    :returns: (the thumbnail's URL, the full-size image's URL, whether a fetch is queued or running, the
        caption)
    """
    task = dss_domain.dss_task(obj)
    if task is None:
        return None, None, False, "DSS image"
    found = dss_image_path(state.data_dir, task)
    if found is not None:
        path, source = found
        label = f"{SOURCE_LABELS[source]['en']} - {task.fov:g}'×{task.fov:g}'"
        full_url = _relative_url(state.data_dir / DSS_DIR, _DSS_PREFIX, path)
        return _thumbnail_url(state.data_dir, path) or full_url, full_url, False, label
    return None, None, state.task_pool.is_pending(dss_key(state.data_dir, task)), "DSS image"


def _thumbnail_url(data_dir: Path, path: Path) -> str | None:
    """The URL of `path`'s shared thumbnail, made first if it is missing or stale; None when making it
    fails (the caller falls back to the full-size image's own URL, see get_dss_status).

    :param data_dir: the data directory
    :param path: the full-size cached DSS image to find or make a thumbnail of
    :returns: the thumbnail's URL, or None
    """
    shared = dss_domain.thumbnail_path(path)
    if not dss_domain.thumbnail_is_current(path, shared):
        try:
            dss_domain.write_thumbnail(path, shared)
        except OSError:
            return None
    return _relative_url(data_dir / DSS_DIR, _DSS_PREFIX, shared)


def get_orbit_status(state: AppState, obj: Object) -> list[tuple[str | None, bool, str]]:
    """One (the orbit diagram's URL once it exists, whether generating it is queued or running, its label)
    per solution of this pair - none when it has no orbit. Same live-check reasoning as get_dss_status;
    state.orbit_elements (which pair this is, if any) is the one part that is safe to have cached per
    Reload, since it never changes while the pool works.

    :param state: the app's shared state
    :param obj: the pair to check
    :returns: (the diagram's URL once it exists, whether generating it is queued or running, its label), one
        per solution
    """
    status = []
    for solution in state.orbit_elements.get(id(obj), []):
        path = orbit_cache_path(state.data_dir, solution)
        label = f"Orbit diagram (solution {solution.number})" if solution.number else "Orbit diagram"
        if path.is_file():
            status.append((_relative_url(state.data_dir / ORBITS_DIR, _ORBITS_PREFIX, path), False, label))
        else:
            status.append((None, state.task_pool.is_pending(str(path)), label))
    return status


def _relative_url(root: Path, prefix: str, path: Path) -> str:
    return f"{prefix}/{path.relative_to(root).as_posix()}"


def get_media_urls(observation: Observation, key: ObservationAttribute) -> list[str]:
    """The URLs of an observation's SKETCH, PHOTOGRAPH or IMAGE files, own or community; empty when it
    has none (a community observation never has IMAGE, so this is always empty for it).

    :param observation: the observation to list media for
    :param key: which kind of media to list - an ObservationAttribute of SKETCH, PHOTOGRAPH or IMAGE
    :returns: the files' URLs
    """
    names = getattr(observation, _MEDIA_ATTRIBUTES[key])
    if not names:
        return []
    if observation.format is None:  # the user's own
        base = f"{_OWNER_PREFIX}/{OWNER_MEDIA_FOLDERS[key]}"
    else:
        assert observation.observer is not None  # set together with format, see Observation
        base = f"/media/{community_media_folder(observation.format, observation.observer.id)}"
    return [f"{base}/{name}" for name in names]
