"""Small builders the unit tests share: hand-made domain objects, and the fixture worlds in tests/fixtures."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from faint_fuzzies.domain.names import set_object_name_abbreviations
from faint_fuzzies.domain.observer import Observer, Scope
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.session import Location, Session
from faint_fuzzies.loading import load_data_dir, load_static_catalogues

FIXTURES = Path(__file__).parents[1] / "fixtures"

HOME = Location("Home", 50.0, 10.0, 100, 1)
OWNER = Observer(id="owner-example", firstname="Owner", surname="Example", scope=Scope.OWNER)


def session(start, end=None, conditions=None):
    """A Session at HOME from `start` to `end` (ISO texts; `end` defaults to `start`)."""
    begin = datetime.fromisoformat(start)
    return Session({}, begin, datetime.fromisoformat(end) if end else begin, HOME, conditions or {})


def fake_collection(catalogues=(), objects=()):
    """Stands in for a Collection where only its catalogue names and its objects are read."""
    return SimpleNamespace(catalogues=[SimpleNamespace(name=name) for name in catalogues], objects=list(objects))


def write_catalogue(directory, name, records):
    """Writes `records` as the catalogue file `name` in `directory`; returns its path."""
    path = Path(directory) / name
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return path


def load_world(data_dir):
    """Everything a data directory loads to, the way the app loads it."""
    root = Path(data_dir)
    return load_data_dir(root, load_static_catalogues(root))


def load_catalogues(*paths, sessions=None):
    """The collection and its references as `filter --catalogue` loads them: the first file is the own catalogue,
    the only one whose values are checked, and no object name abbreviations apply (a data directory loaded by an
    earlier test may have set some)."""
    set_object_name_abbreviations([])
    collection = Collection([load_catalogue(Path(path), sessions, check_values=index == 0)
                             for index, path in enumerate(paths)])
    return collection, References(collection)


def filter_matches(spec, *paths, sessions=None):
    """The Matches of a filter, given as JSON text the way a user writes it, over catalogue files."""
    collection, references = load_catalogues(*paths, sessions=sessions)
    return filter_objects(collection, FilterSpec.from_dict(json.loads(spec)), references)


def filter_labels(spec, *paths, sessions=None):
    """The first names of the Objects a filter matches, in catalogue order."""
    return [match.object.label for match in filter_matches(spec, *paths, sessions=sessions)]


def filter_cases(*rows):
    """Rows of (filter, *expected first names), as pytest cases named after their filter."""
    return [pytest.param(spec, list(expected), id=spec) for spec, *expected in rows]


def find_object(collection, label, catalogue=None):
    """The Object named `label` (of `catalogue`, if given), or - for a Group, which has no names of its own -
    the one whose GROUP is `label`."""
    for obj in collection.objects:
        if catalogue is not None and obj.catalogue != catalogue:
            continue
        if label in obj.names or (not obj.names and label in obj.groups):
            return obj
    raise KeyError(label)


_ORBIT_ERRORS = ((93, "0.5"), (115, "0.02"), (134, "1.5"), (153, "2.0"), (175, "0.3"), (195, "0.01"), (214, "3.0"))


def orbits_file_text(entries, errors=False, header_lines=7):
    """The text of a minimal orbits.txt: `header_lines` blank header lines (real ones are never blank, but a data
    line is recognized by its own shape, not by what precedes it - see domain.orbits._DATA_LINE) and one fixed-width
    line per entry, each a (WDS id, designation, period unit); the other elements are always valid. With `errors`,
    the seven errors are filled in and the axis is in milliarcseconds."""
    def line(wds_id, designation, unit):
        cells = [" "] * 234
        for start, text in ((0, "000000.00+000000.0"), (19, wds_id.removeprefix("WDS")), (30, designation),
                            (80, "100.0"), (92, unit),
                            (105, "1.0"), (114, "a"), (125, "60.0"), (143, "30.0"), (162, "1950.0"),
                            (174, "y"), (187, "0.3"), (205, "45.0"), (233, "3")) + (
                (((114, "m"),) + _ORBIT_ERRORS) if errors else ()):
            cells[start:start + len(text)] = text
        return "".join(cells)
    return "\n".join([""] * header_lines + [line(*entry) for entry in entries]) + "\n"
