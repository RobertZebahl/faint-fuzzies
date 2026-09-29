# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""The rows of the Log page and its filters, without a browser."""
import datetime
from pathlib import Path

from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from faint_fuzzies.tasks import TaskFailure
from faint_fuzzies.ui.browse import find_object
from faint_fuzzies.ui.log import failure_rows, filter_rows, log_rows


def _rows(data_dir):
    root = Path(data_dir)
    data = load_data_dir(root, load_static_catalogues(root))
    return data, log_rows(data.findings)


def log_summary(data_dir):
    """(level, source, row, observation, object, href) of every row, in the order of the page."""
    _data, rows = _rows(data_dir)
    return [(r["level"], r["source"], r["row"], r["observation"], r["object"], r["href"]) for r in rows]


def filtered_objects(data_dir, levels="", sources="", text=""):
    _data, rows = _rows(data_dir)
    split = lambda value: [v for v in value.split(",") if v]
    return [r["object"] for r in filter_rows(rows, split(levels), split(sources), text)]


def found_label(data_dir, reference):
    """The label of the Object a reference `catalogue:record number` names, or None."""
    root = Path(data_dir)
    data = load_data_dir(root, load_static_catalogues(root))
    found = find_object(data.collection, reference)
    return None if found is None else found.label


def failure_summary():
    when = datetime.datetime(2026, 9, 26, 12, 30, 5)
    rows = failure_rows([TaskFailure("a.jpg", "dss", "M 13", "no image", when),
                         TaskFailure("b.jpg", "orbit", "", "boom", when)])
    return [(r["time"], r["kind"], r["what"], r["message"]) for r in rows]
