"""The statistics table of the home page: one row per Object type, the total and each observer, and a footer with
the sums. The numbers are those of `domain.statistics`; the way a cell is written is this page's own. A category's
own label is content, not structure - it comes from site/static/php/page_content.php's category_en/category_de
(see category_label there), not from here."""
from typing import Any

from faint_fuzzies.domain.lists import ListResult
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.domain.statistics import CATEGORY_NAMES, TOTAL, observer_columns, type_table


def home_statistics(result: ListResult, observers: Observers | None) -> dict[str, Any]:
    """The statistics template's values: HEADER_CELLS (the per-observer column headers, after the "Total"
    column the template labels itself), one ROWS entry per category (its key, for category_label, and its
    cells), and FOOTER_CELLS (the grand total row's cells). A cell is "objects (observations)"; an observer
    who observed no object of a type has "-".

    :param result: the Global list's entries
    :param observers: the observers, for the per-observer columns
    :returns: the table's values
    """
    columns = observer_columns(result, observers)
    table = type_table(result, observers)
    total = [0, 0]
    sums = {column["id"]: [0, 0] for column in columns}
    rows = []
    for name in CATEGORY_NAMES:
        row = table[name]
        objects, observations = row[TOTAL]
        total[0] += objects
        total[1] += observations
        cells = []
        for column in columns:
            found = row.get(column["id"], (0, 0))
            cells.append(_cell(found) if found[0] else "-")
            sums[column["id"]][0] += found[0]
            sums[column["id"]][1] += found[1]
        rows.append({"CATEGORY": name, "CELLS": [_cell((objects, observations)), *cells]})
    return {
        "HEADER_CELLS": [column["name"] for column in columns],
        "ROWS": rows,
        "FOOTER_CELLS": [_cell(total), *(_cell(sums[column["id"]]) for column in columns)],
    }


def _cell(counts) -> str:
    return f"{counts[0]} ({counts[1]})"
