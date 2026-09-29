"""The images of an Object on the website, found in the data directory's caches."""
import os
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.domain import dss
from faint_fuzzies.domain.model import Object
from faint_fuzzies.media_pool import dss_cache_dir


@dataclass(frozen=True)
class DssImage:
    """A cached DSS image of an Object, as `get_dss_image` finds it.

    :ivar full: the file name of the full size image, as cached
    :ivar thumbnail: the file name of the small one shown on the page, made when the site is built
    :ivar source: the survey the image was fetched from
    :ivar fov: the field of view, in arcminutes
    """
    full: str
    thumbnail: str
    source: dss.DSSSource
    fov: int


def thumbnail_name(full: str) -> str:
    return f"{full[:-len('.jpg')]}_web.jpg"


def get_dss_image(
    data_dir: Path | None, obj: Object, listings: dict[Path, frozenset[str]] | None = None
) -> DssImage | None:
    """The cached DSS image of an Object, when there is one: of the first survey that has a file. With `listings`
    a folder is listed once, however many Objects look into it (a build asks for every Object of the site, and one
    question per file and Object came to over 100,000 of them); the caller keeps `listings` for as long as the
    folders are not to change.

    :param data_dir: the data directory; None means no image is ever found
    :param obj: the Object to find a cached image of
    :param listings: a cache of directory listings, shared and updated across calls; omit to list the
        directory fresh each time
    :returns: the cached image, or None when there is none
    """
    task = dss.dss_task(obj)
    if task is None or data_dir is None:
        return None
    directory = dss_cache_dir(data_dir, task.catalogue)
    if listings is not None and directory not in listings:
        listings[directory] = frozenset(os.listdir(directory)) if directory.is_dir() else frozenset()
    for source in task.sources:
        name = dss.cache_filename(source, task.position, task.fov)
        found = name in listings[directory] if listings is not None else (directory / name).is_file()
        if found:
            return DssImage(name, thumbnail_name(name), source, int(task.fov))
    return None
