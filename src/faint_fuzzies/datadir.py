"""A data directory: the one place where the own catalogue, the other catalogues, the observers and the files
of the community are found by their names, so the command line needs only its path.

::

    catalogues/<name>.json                                       the external catalogues, converted from their sources
    observations/owner/objects.json                              the own catalogue (required)
    observations/owner/sessions.json                             the sessions
    observations/owner/optic_names.json                          optic code -> readable name (optional)
    observations/owner/object_name_abbreviations.json            catalogue name short forms (optional)
    observations/observers.json                                  the observers (required once there are community files)
    observations/owner/sketches/                                 the user's own Sketch files (SKETCH)
    observations/owner/photographs/                               the user's own Photograph files (PHOTOGRAPH)
    observations/owner/images/                                    the user's own Image files (IMAGE)
    observations/global/<observer>/global.csv                    a folder per Global observer; the folder
                                                                   name is the observer id
    observations/projects/double-stars/<observer>/visual.csv     a folder per observer; the folder name is
                                                                   the observer id
    observations/projects/double-stars/<observer>/photographic.csv
    observations/projects/deep-sky-with-binoculars/<observer>/visual.csv

`catalogues/` and `observations/global/` and `observations/projects/` hold only external data, never the
own catalogue or the owner's own submissions. `observations/owner/` holds everything the user writes by hand:
the own catalogue, the sessions, the optic names, and the Sketch, Photograph and Image files the own
catalogue's observations refer to by name. Nothing else in the directory is read; a folder without the files
above, and a file at a place not listed above, is left alone.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import CatalogueError
from faint_fuzzies.domain.model import ObservationAttribute
from faint_fuzzies.domain.names import set_object_name_abbreviations
from faint_fuzzies.importers.attach import CommunitySource

CATALOGUES = "catalogues"
OBSERVATIONS = "observations"
OWNER = f"{OBSERVATIONS}/owner"
OWN_CATALOGUE = "objects.json"
SESSIONS = "sessions.json"
OPTIC_NAMES = "optic_names.json"
OBJECT_NAME_ABBREVIATIONS = "object_name_abbreviations.json"
OBSERVERS = "observers.json"
GLOBAL = "observations/global"

# the own catalogue's own-image record attributes and the observations/owner/ subfolder each refers to
OWNER_MEDIA_FOLDERS = {ObservationAttribute.SKETCH: "sketches", ObservationAttribute.PHOTOGRAPH: "photographs",
                       ObservationAttribute.IMAGE: "images"}

# the Sixth Catalog of Orbits of Visual Binary Stars, read at runtime only - never converted into a
# stored catalogue (see domain/orbits.py); optional, like optic_names.json
ORBITS_FILE = "catalogues/orbits.txt"

# the order the other catalogues are searched in, and so the order of preference; unknown names come last
CATALOGUE_ORDER = ("ugc", "sac", "herschel", "wds", "gcvs")

# per project folder: the file names of an observer's folder and the format of each
PROJECTS = (
    ("observations/projects/double-stars",
     (("visual.csv", "project-double-stars-visual"), ("photographic.csv", "project-double-stars-photographic"))),
    ("observations/projects/deep-sky-with-binoculars", (("visual.csv", "project-deep-sky-with-binoculars"),)),
)
# the file name and import format of a Global observer's folder under observations/global/
GLOBAL_FILE = "global.csv"
GLOBAL_FORMAT = "global"


@dataclass(frozen=True)
class DataDir:
    """What was found: the catalogue files, the own catalogue first, and everything that belongs to them.

    :ivar catalogues: the catalogue files, the own catalogue first
    :ivar sessions: the sessions file, if there is one
    :ivar observers: the observers file, if there is one
    :ivar sources: the community files found, as CommunitySources
    """
    catalogues: list[Path]
    sessions: Path | None
    observers: Path | None
    sources: list[CommunitySource]


def hand_edited_files(root: Path) -> tuple[Path, Path | None]:
    """The own catalogue and the sessions file, the two files that are written by hand and not converted.

    :param root: the data directory
    :returns: the own catalogue's path, and the sessions file's path if there is one
    :raises faint_fuzzies.domain.findings.CatalogueError: when `root` does not exist, or has no own catalogue
    """
    if not root.is_dir():
        raise CatalogueError(f"data directory {root} does not exist")
    own = root / OWNER / OWN_CATALOGUE
    if not own.is_file():
        raise CatalogueError(f"data directory {root} has no {OWNER}/{OWN_CATALOGUE}, the own catalogue")
    return own, _existing_file(root / OWNER / SESSIONS)


def discover(root: Path) -> DataDir:
    """Finds everything a data directory holds, by the fixed layout this module documents. Also applies
    its object_name_abbreviations.json (see set_object_name_abbreviations) - the one side effect here, but
    every caller that builds a Collection from a data directory goes through this first, and a Collection's
    name matching needs the abbreviations in place before it is built.

    :param root: the data directory
    :returns: what was found
    :raises faint_fuzzies.domain.findings.CatalogueError: when `root` has no own catalogue, or has community
        files but no observers file
    """
    own, sessions = hand_edited_files(root)
    others = [path for path in (root / CATALOGUES).glob("*.json") if path.is_file()]
    catalogues = [own, *sorted(others, key=_catalogue_order)]
    sources = _community_sources(root)

    observers = _existing_file(root / OBSERVATIONS / OBSERVERS)
    if sources and observers is None:
        raise CatalogueError(f"data directory {root} has community files but no {OBSERVATIONS}/{OBSERVERS}")
    set_object_name_abbreviations(read_object_name_abbreviations(root)[0])
    return DataDir(catalogues, sessions, observers, sources)


def _catalogue_order(path: Path) -> tuple[int, str]:
    """The sort key of another catalogue file: by CATALOGUE_ORDER, unknown names last, alphabetically among
    themselves.

    :param path: the catalogue file
    :returns: the sort key
    """
    stem = path.stem
    return CATALOGUE_ORDER.index(stem) if stem in CATALOGUE_ORDER else len(CATALOGUE_ORDER), stem


def _community_sources(root: Path) -> list[CommunitySource]:
    """Every community file found under the project and Global folders, as CommunitySources.

    :param root: the data directory
    :returns: the community files found
    """
    sources = []
    for project, formats in PROJECTS:
        folder = root / project
        for observer in sorted(p for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []:
            sources.extend(CommunitySource(format_name, observer.name, observer / file_name)
                           for file_name, format_name in formats if (observer / file_name).is_file())
    global_folder = root / GLOBAL
    global_observers = sorted(p for p in global_folder.iterdir() if p.is_dir()) if global_folder.is_dir() else []
    sources.extend(CommunitySource(GLOBAL_FORMAT, observer.name, observer / GLOBAL_FILE) for observer in global_observers
                   if (observer / GLOBAL_FILE).is_file())
    return sources


def _existing_file(path: Path) -> Path | None:
    """`path`, if it exists as a file, else None.

    :param path: the candidate path
    :returns: `path`, or None when it is not an existing file
    """
    return path if path.is_file() else None


def optic_names_file(root: Path) -> Path | None:
    """The optic_names.json file, if there is one.

    :param root: the data directory
    :returns: the file's path, or None when there is none
    """
    return _existing_file(root / OWNER / OPTIC_NAMES)


def parse_json_file(path: Path) -> tuple[Any, str | None]:
    """Reads and parses `path` as JSON - the common first step of every optional data-directory JSON file
    (optic_names.json, object_name_abbreviations.json, site/page_descriptions.json): read it, parse it, then
    let the caller check its own shape.

    :param path: the file to read
    :returns: the parsed data, or None and why it could not be read or parsed
    """
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"cannot be read: {exc.strerror if isinstance(exc, OSError) else exc}"


def _optic_names_from(path: Path) -> tuple[dict[str, str], str | None]:
    data, why = parse_json_file(path)
    if why:
        return {}, why
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        return {}, "must be a JSON object of optic codes to names, both strings"
    return data, None


def read_optic_names(root: Path) -> tuple[dict[str, str], str | None]:
    """The optic code -> readable name mapping of optic_names.json, and what is wrong with the file: a missing
    file is not wrong (it is optional) and gives ({}, None); an unreadable or malformed one gives ({}, why).

    :param root: the data directory
    :returns: the mapping (possibly empty), and why it is empty when that is a problem
    """
    path = optic_names_file(root)
    if path is None:
        return {}, None
    return _optic_names_from(path)


def read_optic_names_at(path: Path) -> dict[str, str]:
    """optic_names.json read from exactly `path`, given explicitly (--optic-names): unlike the optional,
    root-relative file (read_optic_names), a file named this way must be usable.

    :param path: the file to read
    :returns: the optic code -> readable name mapping
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read or is malformed
    """
    data, why = _optic_names_from(path)
    if why:
        raise CatalogueError(f"{path}: {why}")
    return data


def object_name_abbreviations_file(root: Path) -> Path | None:
    """The object_name_abbreviations.json file, if there is one.

    :param root: the data directory
    :returns: the file's path, or None when there is none
    """
    return _existing_file(root / OWNER / OBJECT_NAME_ABBREVIATIONS)


def _object_name_abbreviations_from(path: Path) -> tuple[list[tuple[str, list[str]]], str | None]:
    data, why = parse_json_file(path)
    if why:
        return [], why
    if not isinstance(data, list) or not all(
            isinstance(entry, dict) and isinstance(entry.get("pattern"), str)
            and isinstance(entry.get("templates"), list) and entry["templates"]
            and all(isinstance(template, str) for template in entry["templates"]) for entry in data):
        return [], ('must be a JSON array of {"pattern": "...", "templates": ["...", ...]} objects, '
                    "a regular expression and at least one short form each")
    return [(entry["pattern"], entry["templates"]) for entry in data], None


def read_object_name_abbreviations(root: Path) -> tuple[list[tuple[str, list[str]]], str | None]:
    """The (regex pattern, short-form templates) pairs of object_name_abbreviations.json, in the order they
    are written (the first matching entry applies - see domain.names.set_object_name_abbreviations), and
    what is wrong with the file: a missing file is not wrong (it is optional) and gives ([], None); an
    unreadable or malformed one gives ([], why).

    :param root: the data directory
    :returns: the pairs (possibly empty), and why they are empty when that is a problem
    """
    path = object_name_abbreviations_file(root)
    if path is None:
        return [], None
    return _object_name_abbreviations_from(path)


def read_object_name_abbreviations_at(path: Path) -> list[tuple[str, list[str]]]:
    """object_name_abbreviations.json read from exactly `path`, given explicitly
    (--object-name-abbreviations): unlike the optional, root-relative file (read_object_name_abbreviations),
    a file named this way must be usable.

    :param path: the file to read
    :returns: the (regex pattern, short-form templates) pairs, in priority order
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read or is malformed
    """
    data, why = _object_name_abbreviations_from(path)
    if why:
        raise CatalogueError(f"{path}: {why}")
    return data


def owner_media_folder(root: Path, key: ObservationAttribute) -> Path:
    """The observations/owner/ subfolder that the own catalogue's SKETCH, PHOTOGRAPH or IMAGE
    attribute refers files to, by name.

    :param root: the data directory
    :param key: an ObservationAttribute key into OWNER_MEDIA_FOLDERS (SKETCH, PHOTOGRAPH or IMAGE)
    :returns: the subfolder's path
    """
    return root / OWNER / OWNER_MEDIA_FOLDERS[key]


def orbits_file(root: Path) -> Path | None:
    """The orbits.txt file, if there is one.

    :param root: the data directory
    :returns: the file's path, or None when there is none
    """
    return _existing_file(root / ORBITS_FILE)


def community_media_folder(format_name: str, observer_id: str) -> str:
    """The observations/-relative subfolder that a community observer's SKETCH or PHOTOGRAPH files live in
    for the given import format - the same folder each importer resolves file names against.

    :param format_name: the import format
    :param observer_id: the observer's id
    :returns: the subfolder, relative to observations/
    :raises ValueError: when `format_name` is not a known community format
    """
    if format_name == GLOBAL_FORMAT:
        return f"global/{observer_id}/sketches"
    if format_name == "project-deep-sky-with-binoculars":
        return f"projects/deep-sky-with-binoculars/{observer_id}/sketches"
    if format_name == "project-double-stars-visual":
        return f"projects/double-stars/{observer_id}/sketches"
    if format_name == "project-double-stars-photographic":
        return f"projects/double-stars/{observer_id}/photographs"
    raise ValueError(f"unknown community format '{format_name}'")
