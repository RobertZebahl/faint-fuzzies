# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""The Browse page's tables (ui/browse.py) without a browser: each row template draws one cell per column of
its table, in the column order - a missing or extra cell shifts every later value under the wrong header."""
import re
from datetime import datetime

from faint_fuzzies.domain.conditions import ConditionAttribute
from faint_fuzzies.domain.session import Location, Session
from faint_fuzzies.ui.browse import _OBJECT_ROW_BODY, _SESSION_ROW_BODY, OBJECT_COLUMNS, SESSION_COLUMNS, _session_row

_TABLES = {
    "objects": (OBJECT_COLUMNS, _OBJECT_ROW_BODY),
    "sessions": (SESSION_COLUMNS, _SESSION_ROW_BODY),
}
_ROW = re.compile(r"<q-tr\b.*?</q-tr>", re.DOTALL)
_CELL = re.compile(r'<q-td key="(\w+)"[^>]*>(.*?)</q-td>', re.DOTALL)
_VALUE = re.compile(r"\{\{\s*props\.row\.(\w+)\s*\}\}")


def row_template_cell_keys(table):
    """:param table: "objects" or "sessions"
    :returns: the cell keys of each row the table's template draws (one list per <q-tr>)
    """
    _, body = _TABLES[table]
    return [[key for key, _ in _CELL.findall(row)] for row in _ROW.findall(body)]


def column_names(table):
    """:param table: "objects" or "sessions"
    :returns: the names of the table's columns, in order
    """
    columns, _ = _TABLES[table]
    return [column["name"] for column in columns]


def column_labels(table):
    """:param table: "objects" or "sessions"
    :returns: the headers of the table's columns, in order
    """
    columns, _ = _TABLES[table]
    return [column["label"] for column in columns]


def session_list_cells(object_count, **conditions):
    """The session list as it is drawn for one session: the session row's values, in the order the template
    draws its cells, paired with the column headers in their order.

    :param object_count: the number of Objects observed in the session
    :param conditions: its conditions, by ConditionAttribute name (BORTLE=4, SEEING=3/5, ...)
    :returns: a dict of column header -> the value shown under it
    """
    session = Session({}, datetime.fromisoformat("2026-09-01T20:00"), datetime.fromisoformat("2026-09-01T23:30"),
                      Location("Home", 50.0, 10.0, 100, 1),
                      {ConditionAttribute(name): value for name, value in conditions.items()})
    row = _session_row(session, int(object_count))
    (cells,) = [_CELL.findall(r) for r in _ROW.findall(_SESSION_ROW_BODY)]
    shown = [_VALUE.search(content).group(1) for _, content in cells]
    return {label: str(row[field]) for label, field in zip(column_labels("sessions"), shown, strict=True)}
