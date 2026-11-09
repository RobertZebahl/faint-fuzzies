"""Small builders the unit tests share: hand-made domain objects, and the fixture worlds in tests/fixtures."""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from faint_fuzzies.domain.observer import Observer, Scope
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


def find_object(collection, label, catalogue=None):
    """The Object named `label` (of `catalogue`, if given), or - for a Group, which has no names of its own -
    the one whose GROUP is `label`."""
    for obj in collection.objects:
        if catalogue is not None and obj.catalogue != catalogue:
            continue
        if label in obj.names or (not obj.names and label in obj.groups):
            return obj
    raise KeyError(label)
