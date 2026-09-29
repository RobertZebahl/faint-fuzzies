"""The statistics table of the home page: one row per Object type, the total and each observer, and a footer with
the sums. The numbers are those of `domain.statistics`; only the labels and the way a cell is written are this
page's own."""
from faint_fuzzies.domain.lists import ListResult
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.domain.statistics import CATEGORY_NAMES, TOTAL, observer_columns, type_table

LABELS = {  # category -> (English, German)
    "double-stars": ("Double Stars", "Doppelsterne"),
    "asterisms": ("Asterisms", "Sternmuster"),
    "open-clusters": ("Open Clusters", "Offene Sternhaufen"),
    "globular-clusters": ("Globular Clusters", "Kugelsternhaufen"),
    "planetary-nebulae": ("Planetary Nebulas", "Planetarische Nebel"),
    "bright-nebulae": ("Bright Nebulas", "Helle Nebel"),
    "dark-nebulae": ("Dark Nebulas", "Dunkelnebel"),
    "galaxies": ("Galaxies", "Galaxien"),
    "miscellaneous": ("Miscellaneous", "Sonstige"),
}


def home_statistics(result: ListResult, observers: Observers | None, locale: str) -> list[list[str]]:
    """The rows of the table for the template: the header, a row per type, the footer. A cell is "objects
    (observations)"; an observer who observed no object of a type has "-".

    :param result: the Global list's entries
    :param observers: the observers, for the per-observer columns
    :param locale: "en" or "de"
    :returns: the table's rows
    """
    english = locale == "en"
    columns = observer_columns(result, observers)
    table = type_table(result, observers)
    rows = [["", "Total" if english else "Gesamt", *(column["name"] for column in columns)]]
    total = [0, 0]
    sums = {column["id"]: [0, 0] for column in columns}
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
        rows.append([LABELS[name][0 if english else 1], _cell((objects, observations)), *cells])
    rows.append(["", _cell(total), *(_cell(sums[column["id"]]) for column in columns)])
    return rows


def _cell(counts) -> str:
    return f"{counts[0]} ({counts[1]})"
