"""The pages: the page model of a list page (its rows, the table of constellations) for one language.
Plain data again; see objects.py. The menu is in menu.py."""
import itertools
import math
from typing import Any

from faint_fuzzies.domain.lists import Entry
from faint_fuzzies.site.objects import SiteData, object_row
from faint_fuzzies.site.text import escape_html, quote_url


def object_list_page(entries: list[Entry], locale: str, site: SiteData, file: str, name: str,
                     enable_constellation: bool = True, first_name_pattern: str | None = None) -> dict[str, Any]:
    """The values of a list page: `rows` are the values of each object's row, `page` those of the page
    around them. The page's title, description and picture are not here - the template looks them up
    itself from `name` (see site/static/php/page_content.php).

    :param entries: the page's entries
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :param file: the page's file name
    :param name: the page's name, the key its title/description/picture are looked up by
    :param enable_constellation: whether the page starts with the table of constellations to filter by
    :param first_name_pattern: picks the name each row's title shows (see object_row)
    :returns: the page's values
    """
    rows = [object_row(entry, locale, site, first_name_pattern) for entry in entries]
    counts: dict[str, int] = {}
    for row in rows if enable_constellation else []:
        counts[row["OBJECT_CONSTELLATION"]] = counts.get(row["OBJECT_CONSTELLATION"], 0) + 1
    return {
        "file": file, "name": name, "rows": rows,
        "page": {
            "ENGLISH": locale == "en", "LOCALE": locale, "PAGE_KEY": name,
            "ENABLE_CONSTELLATION": enable_constellation,
            "CONST_LIST": constellation_table(counts, file) if enable_constellation else [],
        },
    }


def constellation_table(counts: dict[str, int], file: str) -> list[dict[str, Any]]:
    """The links to the constellations, in at most six rows, filled column by column.

    :param counts: constellation name -> the number of objects shown in it
    :param file: the page's file name, to link back to with a `?constellation=` filter
    :returns: the table's columns, each a list of cells
    """
    columns_max = math.ceil(len(counts) / 6.0)
    table, row = [], []
    for constellation in sorted(counts, key=lambda s: s.lower()):
        row.append({"LINK": f"{quote_url(file)}?constellation={constellation}",
                    "LINK_NAME": escape_html(f"{constellation} ({counts[constellation]})")})
        if len(row) == columns_max:
            table.append(row)
            row = []
    if row:
        table.append(row)
    transposed = [list(column) for column in itertools.zip_longest(*table)]
    return [{"CONST_LIST_COL": [cell for cell in column if cell]} for column in transposed]
