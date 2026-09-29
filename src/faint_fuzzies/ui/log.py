"""The Log page: every Finding about the loaded data at once, and the background tasks (DSS images, orbit diagrams)
that failed. Browse shows the Findings of one Object; this is what to read after a Reload. A row that is about an Object
links to it in Browse, opened in a new tab (the same convention as the Group fact's own links, see
ui.browse._render_group_fact_value), so the Log page itself stays open. Everything follows the loaded data, so a
Reload refreshes it."""
from collections.abc import Iterable
from typing import Any
from urllib.parse import quote

from nicegui import ui

from faint_fuzzies.domain.findings import ERROR, INFO, WARNING, Finding
from faint_fuzzies.domain.model import Object
from faint_fuzzies.finding_index import FindingIndex
from faint_fuzzies.tasks import TaskFailure
from faint_fuzzies.ui.nav import header
from faint_fuzzies.ui.state import AppState

FINDING_COLUMNS = [
    {"name": "level", "label": "Level", "field": "level_rank", "align": "left", "sortable": True},
    {"name": "source", "label": "Source", "field": "source", "align": "left", "sortable": True},
    {"name": "row", "label": "Row", "field": "row", "align": "right", "sortable": True},
    {"name": "observation", "label": "Obs.", "field": "observation", "align": "right", "sortable": True},
    {"name": "object", "label": "Object", "field": "object", "align": "left", "sortable": True},
    {"name": "attribute", "label": "Attribute", "field": "attribute", "align": "left", "sortable": True},
    {"name": "message", "label": "Message", "field": "message", "align": "left"},
]
FAILURE_COLUMNS = [
    {"name": "time", "label": "Time", "field": "time", "align": "left", "sortable": True},
    {"name": "kind", "label": "Task", "field": "kind", "align": "left", "sortable": True},
    {"name": "what", "label": "For", "field": "what", "align": "left", "sortable": True},
    {"name": "message", "label": "What happened", "field": "message", "align": "left"},
]
_FINDING_ROW_BODY = r"""
    <q-tr :props="props">
        <q-td key="level" :props="props" auto-width>
            <q-icon v-if="props.row.level === 'error'" name="error" color="negative" size="sm" />
            <q-icon v-else-if="props.row.level === 'warning'" name="warning" color="warning" size="sm" />
            <q-icon v-else name="info" color="grey-6" size="sm" />
        </q-td>
        <q-td key="source" :props="props">{{ props.row.source }}</q-td>
        <q-td key="row" :props="props">{{ props.row.row }}</q-td>
        <q-td key="observation" :props="props">{{ props.row.observation }}</q-td>
        <q-td key="object" :props="props">
            <a v-if="props.row.href" :href="props.row.href" target="_blank">{{ props.row.object }}</a>
            <span v-else>{{ props.row.object }}</span>
        </q-td>
        <q-td key="attribute" :props="props">{{ props.row.attribute }}</q-td>
        <q-td key="message" :props="props" style="white-space: normal">{{ props.row.message }}</q-td>
    </q-tr>
"""


def object_link(obj: Object) -> str:
    """The address of Browse with this Object found and selected: its catalogue and its record number.

    :param obj: the Object to link to
    :returns: the link's address
    """
    return "/?object=" + quote(f"{obj.catalogue}:{obj.number}", safe="")


_LEVEL_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


def log_rows(findings: FindingIndex) -> list[dict[str, Any]]:
    """The Findings of a loaded data directory as the rows of the table: errors first, then warnings, then info,
    then by source and row. `href` is the link to the Object a row is about, empty for one that is about no
    Object.

    :param findings: the findings to list
    :returns: the table rows
    """
    ordered = sorted(findings.entries, key=lambda entry: (_LEVEL_ORDER.get(entry[0].severity, 0), entry[0].catalogue,
                                                          entry[0].record, entry[0].observation or 0))
    return [_row(number, finding, obj) for number, (finding, obj) in enumerate(ordered)]


def _row(number: int, finding: Finding, obj: Object | None) -> dict[str, Any]:
    return {
        "id": number,
        "level": finding.severity,
        "level_rank": _LEVEL_ORDER.get(finding.severity, 0),
        "source": finding.catalogue,
        "row": finding.record or "",
        "observation": finding.observation or "",
        "object": obj.label if obj is not None else (finding.object or ""),
        "attribute": finding.attribute or "",
        "message": finding.message,
        "href": object_link(obj) if obj is not None else "",
    }


def filter_rows(rows: Iterable[dict[str, Any]], levels: Iterable[str] = (), sources: Iterable[str] = (),
                text: str = "") -> list[dict[str, Any]]:
    """The rows of the given levels and sources (any, when none are given) that have the text in their source, object,
    attribute or message, regardless of case.

    :param rows: the rows to filter, as built by log_rows
    :param levels: the severities to keep; all of them when empty
    :param sources: the catalogues to keep; all of them when empty
    :param text: the text to search for; every row when empty
    :returns: the matching rows
    """
    levels, sources, text = set(levels), set(sources), text.strip().casefold()
    return [row for row in rows
            if (not levels or row["level"] in levels) and (not sources or row["source"] in sources)
            and (not text or any(text in str(row[key]).casefold()
                                  for key in ("source", "object", "attribute", "message")))]


def failure_rows(failures: Iterable[TaskFailure]) -> list[dict[str, Any]]:
    """The failed background tasks as the rows of the failures table.

    :param failures: the failures to list
    :returns: the table rows
    """
    return [{"id": number, "time": f"{failure.time:%H:%M:%S}", "kind": failure.category,
             "what": failure.label or failure.key, "message": failure.message}
            for number, failure in enumerate(failures)]


def build(state: AppState) -> None:
    """Builds the Log page.

    :param state: the app's shared state
    """
    LogPage(state)


class LogPage:
    """The Log page's controller: its NiceGUI elements, and the Finding/failure tables they filter.

    :param state: the app's shared state
    """

    def __init__(self, state: AppState):
        self.state = state
        self._rows: list[dict[str, Any]] = []
        self._failure_count = -1

        header("log", state, self._on_reloaded)
        with ui.column().classes("w-full p-4 gap-3"):
            ui.label("Findings").classes("text-subtitle1")
            with ui.row().classes("w-full items-end gap-3"):
                self.level_select = ui.select({ERROR: "Errors", WARNING: "Warnings", INFO: "Info"}, label="Level",
                                              multiple=True, clearable=True,
                                              on_change=self._apply).classes("w-40").mark("level-select")
                self.source_select = ui.select([], label="Source", multiple=True, clearable=True,
                                               on_change=self._apply).classes("w-64").mark("source-select")
                self.search_input = ui.input(label="Search", on_change=self._apply).classes("w-64").props("clearable")
            self.count_label = ui.label().classes("text-caption")
            self.table = ui.table(columns=FINDING_COLUMNS, rows=[], row_key="id", pagination=50) \
                .classes("w-full").props("dense").mark("findings-table")
            self.table.add_slot("body", _FINDING_ROW_BODY)

            ui.label("Images that could not be made").classes("text-subtitle1")
            self.failure_label = ui.label().classes("text-caption")
            self.failure_table = ui.table(columns=FAILURE_COLUMNS, rows=[], row_key="id", pagination=25) \
                .classes("w-full").props("dense").mark("failures-table")

        # the background tasks go on after the page is open, so what failed since is looked up now and then
        ui.timer(2.0, self._refresh_failures)
        self._load_rows()
        self._refresh_failures()

    def _load_rows(self) -> None:
        """(Re)reads the Finding rows from the current state and reapplies the filters."""
        self._rows = log_rows(self.state.data.findings)
        self.source_select.set_options(sorted({row["source"] for row in self._rows}))
        self.source_select.value = [s for s in self.source_select.value if s in self.source_select.options]
        self._apply()

    def _apply(self) -> None:
        """Reapplies the level/source/search filters to the table and updates the count label."""
        shown = filter_rows(self._rows, self.level_select.value, self.source_select.value,
                            self.search_input.value or "")
        self.table.rows = shown
        self.table.update()
        errors = sum(1 for row in self._rows if row["level"] == ERROR)
        infos = sum(1 for row in self._rows if row["level"] == INFO)
        warnings = len(self._rows) - errors - infos
        self.count_label.text = (f"{len(shown)} of {len(self._rows)} shown: {errors} errors, {warnings} warnings "
                                 f"and {infos} info in all" if self._rows else "No findings.")

    def _refresh_failures(self) -> None:
        """Re-reads the task pool's failures (polled: they accumulate after the page opens) and updates the
        failures table, only touching the UI when the count actually changed."""
        failures = self.state.task_pool.failures()
        if len(failures) == self._failure_count:
            return
        self._failure_count = len(failures)
        self.failure_table.rows = failure_rows(failures)
        self.failure_table.update()
        self.failure_label.text = (f"{len(failures)} of the background tasks since the last Reload did not work."
                                   if failures else "None so far.")

    def _on_reloaded(self) -> None:
        """The header has already reloaded the state (with a progress bar); show what it found."""
        self._failure_count = -1
        self._load_rows()
        self._refresh_failures()
