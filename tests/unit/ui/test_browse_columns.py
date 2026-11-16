"""The Browse page's tables draw each row from a template (ui/browse.py: _OBJECT_ROW_BODY, _SESSION_ROW_BODY) whose
cells must match the table's columns one for one, in order: a missing cell once put the session list's object count
under "Seeing". The session list shows no SQM column (SQM stays in an observation's conditions text)."""
import re

import pytest

from faint_fuzzies.domain.conditions import ConditionAttribute
from faint_fuzzies.ui.browse import _OBJECT_ROW_BODY, _SESSION_ROW_BODY, OBJECT_COLUMNS, SESSION_COLUMNS, _session_row
from tests.unit.builders import session

TABLES = {
    "objects": (OBJECT_COLUMNS, _OBJECT_ROW_BODY),
    "sessions": (SESSION_COLUMNS, _SESSION_ROW_BODY),
}
ROW = re.compile(r"<q-tr\b.*?</q-tr>", re.DOTALL)
CELL = re.compile(r'<q-td key="(\w+)"[^>]*>(.*?)</q-td>', re.DOTALL)
VALUE = re.compile(r"\{\{\s*props\.row\.(\w+)\s*\}\}")


@pytest.mark.parametrize("table", TABLES)
def test_every_row_template_draws_one_cell_per_column_in_column_order(table):
    columns, body = TABLES[table]
    rows = [[key for key, _ in CELL.findall(row)] for row in ROW.findall(body)]
    assert rows
    for keys in rows:
        assert keys == [column["name"] for column in columns]


def test_the_session_list_has_no_sqm_column():
    assert "SQM" not in [column["label"] for column in SESSION_COLUMNS]


def test_each_session_value_is_shown_under_its_own_header():
    conditions = {"BORTLE": "4", "NELM": "6.2", "SQM": "21.3", "SQML": "20.8", "SEEING": "3/5"}
    observed = session("2026-09-01T20:00", "2026-09-01T23:30",
                       {ConditionAttribute(name): value for name, value in conditions.items()})
    row = _session_row(observed, 17)
    (cells,) = [CELL.findall(r) for r in ROW.findall(_SESSION_ROW_BODY)]
    shown = [VALUE.search(content).group(1) for _, content in cells]
    labels = [column["label"] for column in SESSION_COLUMNS]
    by_header = {label: str(row[field]) for label, field in zip(labels, shown, strict=True)}
    assert by_header["Bortle"] == "4"
    assert by_header["NELM"] == "6.2"
    assert by_header["SQML"] == "20.8"
    assert by_header["Seeing"] == "3/5"
    assert by_header["Objects"] == "17"
    assert by_header["Location"] == "Home"
