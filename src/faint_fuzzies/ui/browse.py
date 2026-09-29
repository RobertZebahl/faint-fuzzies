"""The Objects/Sessions browse page: a shared filter, two linked tables, and an in-page detail panel.

Read-only for now: it shows everything a Match/Session/Object/Observation carries, but does not yet let
the user change any of it (that is a separate piece of work, see the project design notes)."""
import html
import json
import re
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Protocol

from nicegui import ui

from faint_fuzzies.domain.catalogue import Catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.conditions import ConditionAttribute
from faint_fuzzies.domain.filters import FilterSpec, FilterSpecError, filter_objects, invalid_objects
from faint_fuzzies.domain.findings import ERROR, INFO, WARNING, Finding
from faint_fuzzies.domain.formats import constellation_name
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType, ObservationAttribute, split_names
from faint_fuzzies.domain.names import component_name
from faint_fuzzies.domain.observation import Grade, Observation, VisibilityEntry, is_header
from faint_fuzzies.domain.observer import OWN_ID, Observer, Observers, Scope
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.seen import seen_status
from faint_fuzzies.domain.session import CONDITION_ATTRIBUTES, Session, SessionAttribute
from faint_fuzzies.finding_index import FindingIndex
from faint_fuzzies.ui.facts import object_facts
from faint_fuzzies.ui.log import object_link
from faint_fuzzies.ui.media import get_dss_status, get_media_urls, get_orbit_status
from faint_fuzzies.ui.nav import header
from faint_fuzzies.ui.state import AppState

# the shaded observations: grey at low opacity, which reads on a light and on a dark theme alike
_SHADE = "background-color: rgba(128, 128, 128, 0.12)"

# thumbnail width; a plain click opens the original in the shared lightbox (see _build_lightbox) instead
# of a new tab - a modified click (the middle button, Ctrl, Cmd, Shift or Alt) still opens a real new tab
_THUMBNAIL_CLASSES = "w-20 rounded"

# runs client-side on every thumbnail's click, so a modified click is never intercepted (there is no way
# to decide that from a Python event handler without first letting the browser already act on the click):
# a plain click is prevented and the clicked link's own href emitted to _open_lightbox; anything else is
# left alone, falling through to the link's own real target="_blank" exactly as without this at all
_LIGHTBOX_CLICK_JS = """(event) => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) {
        return;
    }
    event.preventDefault();
    emit(event.currentTarget.href);
}"""
_LIGHTBOX_FIT_STYLE = "max-width: 90vw; max-height: 85vh;"
_LIGHTBOX_ZOOM_STYLE = "max-width: none; max-height: none;"

# how often the detail panel re-checks a pending DSS image or orbit diagram against disk/the task pool,
# so a fetch that finishes while the panel is open shows up without the user having to re-select the Object
_THUMBNAIL_POLL_INTERVAL = 1.0

OBJECT_COLUMNS = [
    {"name": "finding", "label": "!", "field": "finding_rank", "align": "center", "sortable": True},
    {"name": "notes", "label": "N", "field": "has_notes", "align": "center", "sortable": True},
    {"name": "references", "label": "R", "field": "reference_rank", "align": "center", "sortable": True},
    {"name": "group", "label": "G", "field": "group_rank", "align": "center", "sortable": True},
    {"name": "names", "label": "Name", "field": "names", "align": "left", "sortable": True},
    {"name": "component", "label": "Component", "field": "component", "align": "left", "sortable": True},
    {"name": "catalogue", "label": "Catalogue", "field": "catalogue", "align": "center", "sortable": True},
    {"name": "types", "label": "Type", "field": "types", "align": "center", "sortable": True},
    {"name": "constellation", "label": "Constellation", "field": "constellation", "align": "center", "sortable": True},
    {"name": "magnitude", "label": "Magnitude", "field": "magnitude", "align": "center", "sortable": True},
    {"name": "size", "label": "Size / Separation", "field": "size", "align": "center", "sortable": True},
    {"name": "observations", "label": "Observations", "field": "observations", "align": "center", "sortable": True},
]
SESSION_COLUMNS = [
    {"name": "date", "label": "Date", "field": "date", "align": "left", "sortable": True},
    {"name": "time", "label": "Time", "field": "time", "align": "left", "sortable": True},
    {"name": "location", "label": "Location", "field": "location", "align": "left", "sortable": True},
    {"name": "bortle", "label": "Bortle", "field": "bortle", "align": "center", "sortable": True},
    {"name": "nelm", "label": "NELM", "field": "nelm", "align": "center", "sortable": True},
    {"name": "sqm", "label": "SQM", "field": "sqm", "align": "center", "sortable": True},
    {"name": "sqml", "label": "SQML", "field": "sqml", "align": "center", "sortable": True},
    {"name": "seeing", "label": "Seeing", "field": "seeing", "align": "center", "sortable": True},
    {"name": "objects", "label": "Objects", "field": "objects", "align": "center", "sortable": True},
]
# Shown above the advanced filter's JSON textarea. Merged over the fields above (same key wins); the criteria
# are the same `filter`/`validate` take on the command line (see the README's "Filter specification"), which
# has the full list - this is only a handful of the ones the plain fields above don't cover.
_ADVANCED_FILTER_HELP = """\
Examples:

- `{"seen": ["not_observed"]}` — not yet observed
- `{"finding": ["error", "warning", "info"]}` — anything with a Finding
- `{"header_only": true}` — has a Header but is not published
- `{"publish_without_observation": true}` — published without an Observation
- `{"follow_references": true}` — counts a referenced object's Observations as the object's own
- `{"size_ratio": [5, null]}` — thin galaxies (axis ratio 1:5 or more)

All criteria (see the README's "Filter specification" for the full detail). AND across criteria, OR within
one; an object matches when any one of its observations satisfies every observation criterion at once.

**Object**

- `name`, `group`, `name_group` — string or list, exact, case-insensitive; `name_group` matches either
  the name or the group, for a value that should find an object whether it turns out to be a Group or a
  pair with no Group of its own
- `name_pattern`, `group_pattern`, `name_group_pattern`, `constellation_pattern` — regular expression,
  must match the whole value; `name_group_pattern` is the pattern version of `name_group` (also used by
  the filter bar's own Name/Group Pattern field below, for the same reason)
- `catalogue` — string or list, e.g. `"wds.json"`
- `type`, `type_exclude` — string or list of type codes
- `constellation` — string or list
- `is_group` — true/false
- `exclude_group_members` — true/false, hides a double star pair that is a member of a matched group
  (never any other kind of Group member)
- `size_ratio` — `[min, max]`
- `size` — `[min, max]` in arcminutes, or `{"range": [min, max], "axis": "major"|"minor"}` to pick one
  dimension (default is the smaller of the two - every direction at least that big, not just the longest
  axis; no minor of its own is treated as circular, unless axis is "minor"); never through a reference
- `magnitude` — `[min, max]`, or `{"range": [min, max], "band": "v"|"b"|"p"}` to pick a specific value (default
  is visual, then blue, then whatever is first); through the reference when the object itself has none; a
  double star needs every component (primary and secondary) in range, not just one
- `magnitude_delta` — same shape as `magnitude`, but for `|primary - secondary|`; never matches anything
  without exactly two components
- `separation` — `[min, max]` in arcseconds, a double star's separation, likewise through the reference
- `rating` — `[min, max]`, the Object's general RATING, used by every Project (Double Stars included) the same way
- `binocular_rating` — `[min, max]`, the separate Deep Sky With Binoculars rating
- `has_notes` — true/false, whether the record carries a non-empty NOTES
- `seen` — list of `not_observed`, `failed`, `seen`
- `project` — one of `global`, `project-double-stars`, `project-deep-sky-with-binoculars`
- `follow_references` — true/false
- `finding` — list of `error`, `warning`, `info` (needs `--data-dir`)
- `header_only`, `publish_without_observation` — true/false

**Observation** (all must hold for the same observation)

- `observer` — list of observer ids
- `scope` — list of `OWNER`, `GLOBAL`, `PROJECT` (an observation with no observer counts as `OWNER`)
- `method` — list of `visual`, `photographic`
- `public` — true/false
- `optic_type` — list of `naked_eye`, `binoculars`, `telescope`
- `aperture` — `[min, max]` in mm
- `date` — `["2020-01-01", null]`, private observations only
- `has_sketch`, `has_photograph`, `has_image` — true/false
- `public_grade` — list of `EASY`, `MEDIUM`, `HARD`, `FAILED`, `RED`, `ORANGE`
- `private_grade` — `[min, max]`
- `session` — the ISO start of a Session, e.g. `"2020-01-15T20:30"`
"""
# A body row that selects on a click anywhere in it, and is coloured by the row's "color" field. It keeps
# the selection checkbox as the first cell (its own click stopped from bubbling) because selection="single"
# makes Quasar's default header include one leading checkbox column; a body without a matching leading
# cell shifts every other cell one column to the left of its header.
_OBJECT_ROW_BODY = r"""
    <q-tr :props="props" @click="props.selected = true" style="cursor: pointer" :style="{color: props.row.color}">
        <q-td auto-width @click.stop>
            <q-checkbox v-model="props.selected" />
        </q-td>
        <q-td key="finding" :props="props" auto-width>
            <q-icon v-if="props.row.finding === 'error'" name="error" color="negative" size="sm">
                <q-tooltip>{{ props.row.finding_text }}</q-tooltip>
            </q-icon>
            <q-icon v-else-if="props.row.finding === 'warning'" name="warning" color="warning" size="sm">
                <q-tooltip>{{ props.row.finding_text }}</q-tooltip>
            </q-icon>
            <q-icon v-else-if="props.row.finding === 'info'" name="info" color="grey-6" size="sm">
                <q-tooltip>{{ props.row.finding_text }}</q-tooltip>
            </q-icon>
        </q-td>
        <q-td key="notes" :props="props" auto-width>
            <q-avatar v-if="props.row.has_notes" size="20px" color="green-6" text-color="white">
                <span style="font-size: 11px; font-weight: bold">N</span>
                <q-tooltip>{{ props.row.notes_text }}</q-tooltip>
            </q-avatar>
        </q-td>
        <q-td key="references" :props="props" auto-width @click.stop>
            <q-avatar v-if="props.row.has_references" size="20px" color="grey-7" text-color="white"
                     style="cursor: pointer"
                     @click="props.row.ref_expand = !props.row.ref_expand">
                <span style="font-size: 11px; font-weight: bold">R</span>
                <q-tooltip>{{ props.row.reference_tooltip }}</q-tooltip>
            </q-avatar>
        </q-td>
        <q-td key="group" :props="props" auto-width @click.stop>
            <q-avatar v-if="props.row.is_group" size="20px" color="primary" text-color="white"
                     :style="{cursor: props.row.members.length ? 'pointer' : 'default', opacity: props.row.members.length ? 1 : 0.35}"
                     @click="props.row.members.length && (props.expand = !props.expand)">
                <span style="font-size: 11px; font-weight: bold">G</span>
                <q-tooltip>{{ props.row.group_tooltip }}</q-tooltip>
            </q-avatar>
        </q-td>
        <q-td key="names" :props="props">{{ props.row.names }}</q-td>
        <q-td key="component" :props="props">{{ props.row.component }}</q-td>
        <q-td key="catalogue" :props="props">{{ props.row.catalogue }}</q-td>
        <q-td key="types" :props="props">{{ props.row.types }}</q-td>
        <q-td key="constellation" :props="props">{{ props.row.constellation }}</q-td>
        <q-td key="magnitude" :props="props">{{ props.row.magnitude }}</q-td>
        <q-td key="size" :props="props">{{ props.row.size }}</q-td>
        <q-td key="observations" :props="props">{{ props.row.observations }}</q-td>
    </q-tr>
    <template v-if="props.row.is_group" v-for="member in props.row.members" :key="member.id">
        <q-tr v-show="props.expand" style="cursor: pointer" :style="{color: member.color}"
             @click="() => $parent.$emit('member_click', member)">
            <q-td auto-width></q-td>
            <q-td key="finding" :props="props" auto-width>
                <q-icon v-if="member.finding === 'error'" name="error" color="negative" size="xs">
                    <q-tooltip>{{ member.finding_text }}</q-tooltip>
                </q-icon>
                <q-icon v-else-if="member.finding === 'warning'" name="warning" color="warning" size="xs">
                    <q-tooltip>{{ member.finding_text }}</q-tooltip>
                </q-icon>
                <q-icon v-else-if="member.finding === 'info'" name="info" color="grey-6" size="xs">
                    <q-tooltip>{{ member.finding_text }}</q-tooltip>
                </q-icon>
            </q-td>
            <q-td key="notes" :props="props" auto-width>
                <q-avatar v-if="member.has_notes" size="16px" color="green-6" text-color="white">
                    <span style="font-size: 9px; font-weight: bold">N</span>
                    <q-tooltip>{{ member.notes_text }}</q-tooltip>
                </q-avatar>
            </q-td>
            <q-td key="references" :props="props" auto-width></q-td>
            <q-td key="group" :props="props" auto-width></q-td>
            <q-td key="names" :props="props" style="padding-left: 32px">{{ member.names }}</q-td>
            <q-td key="component" :props="props">{{ member.component }}</q-td>
            <q-td key="catalogue" :props="props">{{ member.catalogue }}</q-td>
            <q-td key="types" :props="props">{{ member.types }}</q-td>
            <q-td key="constellation" :props="props">{{ member.constellation }}</q-td>
            <q-td key="magnitude" :props="props">{{ member.magnitude }}</q-td>
            <q-td key="size" :props="props">{{ member.size }}</q-td>
            <q-td key="observations" :props="props">{{ member.observations }}</q-td>
        </q-tr>
    </template>
    <template v-if="props.row.has_references" v-for="reference in props.row.references" :key="reference.id">
        <q-tr v-show="props.row.ref_expand" style="cursor: pointer" :style="{color: reference.color}"
             @click="() => $parent.$emit('reference_click', reference)">
            <q-td auto-width></q-td>
            <q-td key="finding" :props="props" auto-width>
                <q-icon v-if="reference.finding === 'error'" name="error" color="negative" size="xs">
                    <q-tooltip>{{ reference.finding_text }}</q-tooltip>
                </q-icon>
                <q-icon v-else-if="reference.finding === 'warning'" name="warning" color="warning" size="xs">
                    <q-tooltip>{{ reference.finding_text }}</q-tooltip>
                </q-icon>
                <q-icon v-else-if="reference.finding === 'info'" name="info" color="grey-6" size="xs">
                    <q-tooltip>{{ reference.finding_text }}</q-tooltip>
                </q-icon>
            </q-td>
            <q-td key="notes" :props="props" auto-width>
                <q-avatar v-if="reference.has_notes" size="16px" color="green-6" text-color="white">
                    <span style="font-size: 9px; font-weight: bold">N</span>
                    <q-tooltip>{{ reference.notes_text }}</q-tooltip>
                </q-avatar>
            </q-td>
            <q-td key="references" :props="props" auto-width></q-td>
            <q-td key="group" :props="props" auto-width></q-td>
            <q-td key="names" :props="props" style="padding-left: 32px">{{ reference.names }}</q-td>
            <q-td key="component" :props="props">{{ reference.component }}</q-td>
            <q-td key="catalogue" :props="props">{{ reference.catalogue }}</q-td>
            <q-td key="types" :props="props">{{ reference.types }}</q-td>
            <q-td key="constellation" :props="props">{{ reference.constellation }}</q-td>
            <q-td key="magnitude" :props="props">{{ reference.magnitude }}</q-td>
            <q-td key="size" :props="props">{{ reference.size }}</q-td>
            <q-td key="observations" :props="props">{{ reference.observations }}</q-td>
        </q-tr>
    </template>
"""
_SESSION_ROW_BODY = r"""
    <q-tr :props="props" @click="props.selected = true" style="cursor: pointer" :style="{color: props.row.color}">
        <q-td auto-width @click.stop>
            <q-checkbox v-model="props.selected" />
        </q-td>
        <q-td key="date" :props="props">{{ props.row.date }}</q-td>
        <q-td key="time" :props="props">{{ props.row.time }}</q-td>
        <q-td key="location" :props="props">{{ props.row.location }}</q-td>
        <q-td key="bortle" :props="props">{{ props.row.bortle }}</q-td>
        <q-td key="nelm" :props="props">{{ props.row.nelm }}</q-td>
        <q-td key="sqml" :props="props">{{ props.row.sqml }}</q-td>
        <q-td key="seeing" :props="props">{{ props.row.seeing }}</q-td>
        <q-td key="objects" :props="props">{{ props.row.objects }}</q-td>
    </q-tr>
"""


def build(state: AppState, focus: str | None = None) -> None:
    """Builds the Browse page.

    :param state: the app's shared state
    :param focus: a `catalogue:record number` reference to open and select on load, if any
    """
    BrowsePage(state, focus)


def find_object(collection: Collection, reference: str) -> Object | None:
    """The Object a reference `catalogue:record number` names (the address the Log page links to), valid or Invalid.

    :param collection: the collection to search
    :param reference: the reference to resolve
    :returns: the Object, or None when the reference is malformed or names no Object
    """
    name, _, number = reference.rpartition(":")
    if not number.isdigit():
        return None
    wanted = int(number)
    for catalogue in collection.catalogues:
        if catalogue.name == name:
            return next((o for o in (*catalogue.objects, *catalogue.invalid) if o.number == wanted), None)
    return None


class BrowsePage:
    """The Browse page's controller: the shared filter bar, the Objects and Sessions tables it drives, and
    the detail panel that shows a selected Object or Session.

    :param state: the app's shared state
    :param focus: a reference `catalogue:record number`: the page then opens on that Object
    """
    catalogue_select: ui.select
    name_input: ui.input
    type_select: ui.select
    constellation_select: ui.select
    observer_select: ui.select
    advanced_input: ui.textarea

    def __init__(self, state: AppState, focus: str | None = None):
        self.state = state
        self.selected_session: Session | None = None
        self._objects_by_id: dict[int, Object] = {}
        self._sessions_by_id: dict[int, Session] = {}
        self._finding_filter: list[str] = []  # set by _filter_by_finding, cleared by _clear_finding_filter
        # the Object _render_thumbnails polls for, or None (a Session shown instead)
        self._shown_object: Object | None = None
        self._thumbnail_container: ui.column | None = None
        self._thumbnails_pending = False  # sidesteps _poll_thumbnails checking disk/the task pool every tick
        self._thumbnail_signature: tuple | None = None  # what is currently on screen; see _render_thumbnails
        self._default_catalogue: list[str] = []  # restored by _reset_filter, not just an empty selection
        self._default_observer: list[str] = []  # restored by _reset_filter, not just an empty selection
        self._build_lightbox()

        header("browse", state, self._on_reloaded)

        with ui.splitter(value=70, limits=(30, 100)).classes("w-full").style("height: calc(100vh - 90px)") as splitter:
            with splitter.before, ui.column().classes("w-full max-w-full p-4 gap-3 h-full").style("overflow-y: auto"):
                self._build_filter_bar()

                self.session_expansion = ui.expansion(icon="calendar_month").classes("w-full")
                with self.session_expansion:
                    self.session_banner = ui.row().classes("items-center gap-2")
                    self.sessions_table = ui.table(
                        columns=SESSION_COLUMNS, rows=[], row_key="id", selection="single",
                        pagination=5, on_select=self._on_session_select,
                    ).classes("w-full").props("dense").mark("sessions-table")
                    self.sessions_table.add_slot("body", _SESSION_ROW_BODY)

                self.objects_label = ui.label("Objects").classes("text-subtitle1")
                self.finding_summary = ui.row().classes("items-center gap-1")
                self.objects_table = ui.table(
                    columns=OBJECT_COLUMNS, rows=[], row_key="id", selection="single",
                    pagination=25, on_select=self._on_object_select,
                ).classes("w-full").props("dense").mark("objects-table")
                self.objects_table.add_slot("body", _OBJECT_ROW_BODY)
                self.objects_table.on("member_click", self._on_member_click)
                self.objects_table.on("reference_click", self._on_reference_click)
            with splitter.after, ui.column().classes("w-full h-full q-pa-md gap-2").style("overflow-y: auto"):
                self.detail = ui.column().classes("w-full gap-2")
                with self.detail:
                    ui.label("Select an object or a session to see its details.").classes("text-caption")

        self._render_session_banner()
        self._refresh_sessions()
        self._render_finding_summary()
        self._apply_filter()
        ui.timer(_THUMBNAIL_POLL_INTERVAL, self._poll_thumbnails)
        if focus:
            self._focus(focus)

    def _focus(self, reference: str) -> None:
        """Filters down to one Object (by its catalogue and its first name, or its group, when it has one) and
        selects it.

        :param reference: a `catalogue:record number` reference, as find_object takes
        """
        obj = find_object(self.state.data.collection, reference)
        if obj is None:
            ui.notify(f"There is no object {reference}.", type="warning")
            return
        self.catalogue_select.value = [obj.catalogue]
        for select in (self.type_select, self.constellation_select, self.observer_select):
            select.value = []
        self._finding_filter = []
        first = obj.names[0] if obj.names else (obj.groups[0] if obj.groups else None)
        self.name_input.value = re.escape(first) if first else ""
        self.advanced_input.value = ""
        self._apply_filter()
        self._show_object(obj)
        row = next((r for r in self.objects_table.rows if r["id"] == id(obj)), None)
        if row is not None:
            self.objects_table.selected = [row]
            self.objects_table.update()

    # ---- filter bar ----------------------------------------------------

    def _build_filter_bar(self) -> None:
        """Builds the filter bar's fields, defaulting Catalogue to the own catalogue plus the WDS and
        Observer to the owner, when more than one catalogue is loaded (see `_default_catalogues` and
        `_default_observers`, both restored by `_reset_filter`)."""
        collection = self.state.data.collection
        catalogues = sorted({c.name for c in collection.catalogues})
        types = sorted({t.value for obj in collection.objects for t in obj.types})
        constellations = sorted({_canonical_constellation(obj.constellation)
                                 for obj in collection.objects if obj.constellation})
        observers = _observer_options(collection, self.state.data.observers)
        own_catalogue = _default_catalogues(collection)
        self._default_catalogue = own_catalogue
        default_observer = _default_observers(collection, self.state.data.observers, observers)
        self._default_observer = default_observer

        with ui.row().classes("w-full items-end gap-3"):
            self.catalogue_select = ui.select(catalogues, label="Catalogue", value=own_catalogue, multiple=True,
                                              clearable=True).classes("w-40")
            self.name_input = ui.input(label="Name/Group Pattern").classes("w-40") \
                .on("keydown.enter", self._apply_filter)
            self.type_select = ui.select(types, label="Type", multiple=True, clearable=True, with_input=True) \
                .classes("w-40")
            self.constellation_select = ui.select(constellations, label="Constellation", multiple=True,
                                                   clearable=True, with_input=True).classes("w-40")
            self.observer_select = ui.select(observers, label="Observer", value=default_observer, multiple=True,
                                             clearable=True, on_change=self._deselect_observer_separator) \
                .classes("w-40").mark("observer-select")
            ui.button("Apply filter", icon="search", on_click=self._apply_filter)
            ui.button("Reset filter", icon="restart_alt", on_click=self._reset_filter) \
                .props("flat").mark("reset-filter-button")
        ui.label("Advanced filter (JSON, merged over the fields above)").classes("text-caption")
        self.advanced_input = ui.textarea(placeholder='{"follow_references": true}').classes("w-full") \
            .props("rows=1")
        with ui.expansion("Show all criteria").classes("w-full"):
            ui.markdown(_ADVANCED_FILTER_HELP).classes("text-caption")

    def _build_spec_dict(self) -> dict:
        """The filter bar's fields (plus the advanced JSON and the selected Session, if any) merged into one
        FilterSpec dict, the advanced JSON winning on a shared key.

        :returns: the merged spec dict
        :raises json.JSONDecodeError: when the advanced filter field is not valid JSON
        :raises FilterSpecError: when the advanced filter is valid JSON but not a JSON object
        """
        spec: dict = {}
        if self.catalogue_select.value:
            spec["catalogue"] = self.catalogue_select.value
        if self.name_input.value:
            spec["name_group_pattern"] = self.name_input.value
        if self.type_select.value:
            spec["type"] = self.type_select.value
        if self.constellation_select.value:
            spec["constellation"] = self.constellation_select.value
        wanted_observers = [v for v in self.observer_select.value if v]  # "" is the separator, never a real id
        if wanted_observers:
            spec["observer"] = wanted_observers
        if self._finding_filter:
            spec["finding"] = self._finding_filter
        if self.advanced_input.value and self.advanced_input.value.strip():
            advanced = json.loads(self.advanced_input.value)  # FilterSpecError below covers a bad shape
            if not isinstance(advanced, dict):
                raise FilterSpecError("the advanced filter must be a JSON object")
            spec.update(advanced)
        if self.selected_session is not None:
            iso = _session_key(self.selected_session)
            existing = spec.get("session", [])
            existing = [existing] if isinstance(existing, str) else list(existing)
            spec["session"] = [*existing, iso]
        return spec

    def _deselect_observer_separator(self) -> None:
        """The "── project observers ──" divider uses "" as its value so it can never match a real
        observer; if it gets picked anyway (it is a plain, clickable option), drop it right away."""
        if "" in self.observer_select.value:
            self.observer_select.value = [v for v in self.observer_select.value if v]

    def _reset_filter(self) -> None:
        """Restores every field of the filter bar to what it showed when the page first opened - Catalogue
        and Observer to their smart defaults (see _build_filter_bar), everything else empty - and clears
        the "N errors/warnings" quick filter too, so it lines up with what the bar itself now shows. The
        selected Session, which has its own Clear button in the session banner, is left alone."""
        self.catalogue_select.value = list(self._default_catalogue)
        self.observer_select.value = list(self._default_observer)
        self.name_input.value = ""
        for select in (self.type_select, self.constellation_select):
            select.value = []
        self.advanced_input.value = ""
        self._finding_filter = []
        self._render_finding_summary()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Builds the filter from the bar's current fields and re-fills the Objects table with its matches
        (invalid Objects first), plus every member/reference a match needs to show even if the filter itself
        would not have matched them."""
        try:
            spec_dict = self._build_spec_dict()
            spec = FilterSpec.from_dict(spec_dict)
        except (FilterSpecError, json.JSONDecodeError) as exc:
            ui.notify(f"Filter: {exc}", type="negative")
            return
        data = self.state.data
        findings = data.findings
        try:
            matches = filter_objects(data.collection, spec, data.references, data.observers, findings)
            invalid = invalid_objects(data.collection, spec, data.references, data.observers, findings)
        except FilterSpecError as exc:
            ui.notify(f"Filter: {exc}", type="negative")
            return
        if self.selected_session is not None:
            matches = sorted(matches, key=lambda m: _earliest_in_session(m, self.selected_session))
        self._objects_by_id = {id(o): o for o in invalid} | {id(m.object): m.object for m in matches}
        # a Group's members are shown (and so must be clickable) whether or not the current filter would
        # itself have matched them - membership does not depend on it, see _group_columns
        for match in matches:
            for member in data.collection.members_of(match.object):
                self._objects_by_id.setdefault(id(member), member)
            for reference in data.references.of(match.object):
                self._objects_by_id.setdefault(id(reference), reference)
        # the Objects that cannot be used come first: they are the ones to look at
        self.objects_table.rows = [_invalid_row(o, findings) for o in invalid] + [
            _object_row(m, data.collection, data.references, findings) for m in matches]
        self.objects_table.update()
        self.objects_label.text = f"Objects ({len(self.objects_table.rows)})"

    # ---- sessions --------------------------------------------------------

    def _refresh_sessions(self) -> None:
        """Re-fills the Sessions table from the current state, most recent session first."""
        sessions = self.state.data.sessions
        rows = []
        self._sessions_by_id = {}
        if sessions is not None:
            counts = _session_object_counts(self.state.data.collection)
            for session in reversed(sessions.sessions):  # most recent first
                self._sessions_by_id[id(session)] = session
                rows.append(_session_row(session, counts.get(id(session), 0)))
        self.sessions_table.rows = rows
        self.sessions_table.update()

    def _render_finding_summary(self) -> None:
        """How many Objects of the own catalogue are at each level, as buttons that filter to them, and - once
        one has been clicked - a note of which level the Objects table is narrowed to, with a way to clear it
        (there is no dedicated Findings field in the filter bar any more, see _filter_by_finding)."""
        collection, findings = self.state.data.collection, self.state.data.findings
        own = collection.catalogues[0]
        invalid = len(own.invalid)
        errors = invalid + sum(1 for o in own.objects if findings.severity(o) == ERROR)
        warnings = sum(1 for o in own.objects if findings.severity(o) == WARNING)
        infos = sum(1 for o in own.objects if findings.severity(o) == INFO)
        self.finding_summary.clear()
        with self.finding_summary:
            ui.label("Own catalogue:").classes("text-caption")
            if not errors and not warnings and not infos:
                ui.label("no findings").classes("text-caption")
            else:
                if errors:
                    ui.button(f"{errors} with errors" + (f" ({invalid} invalid)" if invalid else ""), icon="error",
                              on_click=lambda: self._filter_by_finding(ERROR)
                              ).props("flat dense no-caps color=negative")
                if warnings:
                    ui.button(f"{warnings} with warnings", icon="warning",
                              on_click=lambda: self._filter_by_finding(WARNING)
                              ).props("flat dense no-caps color=warning")
                if infos:
                    ui.button(f"{infos} with info", icon="info",
                              on_click=lambda: self._filter_by_finding(INFO)).props("flat dense no-caps color=grey-6")
            if self._finding_filter:
                labels = {ERROR: "errors", WARNING: "warnings", INFO: "info"}
                shown = " and ".join(labels[level] for level in self._finding_filter)
                ui.label(f"Showing only {shown}.").classes("text-caption")
                ui.button("Clear", icon="close", on_click=self._clear_finding_filter).props("flat dense")

    def _filter_by_finding(self, level: str) -> None:
        """Shows the Objects of the own catalogue at this level, whatever the filter bar asked for before.

        :param level: the Finding severity to show, ERROR/WARNING/INFO
        """
        self._finding_filter = [level]
        self.catalogue_select.value = [self.state.data.collection.catalogues[0].name]
        self._render_finding_summary()
        self._apply_filter()

    def _clear_finding_filter(self) -> None:
        self._finding_filter = []
        self._render_finding_summary()
        self._apply_filter()

    def _render_session_banner(self) -> None:
        sessions = self.state.data.sessions
        total = len(sessions.sessions) if sessions is not None else 0
        if self.selected_session is None:
            self.session_expansion.text = f"Sessions ({total}) — none selected"
        else:
            self.session_expansion.text = f"Sessions ({total}) — filtered to {_session_key(self.selected_session)}"
        self.session_banner.clear()
        with self.session_banner:
            if self.selected_session is None:
                ui.label("Select a session below to filter Objects down to it.").classes("text-caption")
            else:
                ui.label(f"Showing only objects with an observation in session "
                         f"{_session_key(self.selected_session)}.").classes("text-body2")
                ui.button("Clear", icon="close", on_click=self._clear_session).props("flat dense")

    def _clear_session(self) -> None:
        self.selected_session = None
        self.sessions_table.selected = []
        self._render_session_banner()
        self._apply_filter()

    # ---- selection handlers ----------------------------------------------

    def _on_object_select(self, event) -> None:
        if not event.selection:
            return
        obj = self._objects_by_id.get(event.selection[0]["id"])
        if obj is not None:
            self._show_object(obj)

    def _on_member_click(self, event) -> None:
        """A member row clicked inside an expanded Group (see _OBJECT_ROW_BODY's "member_click" emit):
        opens its detail panel exactly as selecting it from the main list would."""
        obj = self._objects_by_id.get(event.args["id"])
        if obj is not None:
            self._show_object(obj)

    def _on_reference_click(self, event) -> None:
        """A reference row clicked inside an expanded References list (see _OBJECT_ROW_BODY's "reference_click"
        emit): opens its detail panel exactly as selecting it from the main list would."""
        obj = self._objects_by_id.get(event.args["id"])
        if obj is not None:
            self._show_object(obj)

    def _on_session_select(self, event) -> None:
        """A Sessions table row selected: filters Objects down to it and shows its detail panel."""
        if not event.selection:
            return
        session = self._sessions_by_id.get(event.selection[0]["id"])
        if session is None:
            return
        self.selected_session = session
        self._render_session_banner()
        self._apply_filter()
        self._show_session(session)

    # ---- detail panel ------------------------------------------------------

    def _show_object(self, obj: Object) -> None:
        """Replaces the detail panel with this Object's findings, facts, thumbnails and observations
        (split into this session's, when one is selected, and the rest).

        :param obj: the Object to show
        """
        if obj.valid:
            self.state.bump(obj)
        self._shown_object = None
        self._thumbnail_container = None
        self._thumbnail_signature = None
        self.detail.clear()
        with self.detail:
            with ui.row().classes("items-center gap-2"):
                ui.label(obj.display_name).classes("text-h6")
                if obj.is_group:
                    with ui.element("q-avatar").props("size=20px color=primary text-color=white"):
                        ui.label("G").style("font-size: 11px; font-weight: bold")
                        ui.tooltip("Group")
            self._findings_panel(obj)
            self._facts_panel(obj)
            if obj.valid:
                self._thumbnail_container = ui.column().classes("gap-0")
                self._shown_object = obj
                self._render_thumbnails(obj)
            ui.separator()

            all_observations = list(obj.all_observations)
            session_observations = [o for o in all_observations
                                    if self.selected_session is not None and o.session is self.selected_session]
            session_ids = {id(o) for o in session_observations}
            remaining = [o for o in all_observations if id(o) not in session_ids]

            if session_observations:
                ui.label(f"This session ({len(session_observations)})").classes("text-subtitle2")
                self._observation_list(session_observations)

            # the Header is listed with the observations but is not one: it is left out of the counts
            ui.label(f"Observations ({_count(all_observations)})").classes("text-subtitle2")
            for group_label, group_observations in _grouped_observations(remaining):
                with ui.expansion(f"{group_label} ({_count(group_observations)})", value=False).classes("w-full"):
                    self._observation_list(group_observations)

    def _facts_panel(self, obj: Object) -> None:
        """Everything the record says about the Object, as labeled values; a value a double star takes from
        the entry it references is marked with that catalogue. An Invalid Object has no references and no
        Seen status.

        :param obj: the Object to describe
        """
        data = self.state.data
        seen = seen_status(obj, list(obj.all_observations)) if obj.valid else None
        with ui.grid(columns="max-content 1fr").classes("w-full gap-x-4 gap-y-0"):
            for fact in object_facts(obj, data.references if obj.valid else None, seen):
                ui.label(fact.label).classes("text-caption text-grey-7")
                if fact.label == "Group":
                    self._render_group_fact_value(obj, data.collection)
                else:
                    ui.label(f"{fact.value} (from {fact.source})" if fact.source else fact.value) \
                        .classes("text-body2").style("white-space: pre-line")

    def _render_group_fact_value(self, obj: Object, collection: Collection) -> None:
        """The Group fact's value: each group name, linked to its Group Object (opened in a new tab) when it
        names exactly one - a Group name with none, or more than one, of its own stays plain text (see
        _group_links).

        :param obj: the Object whose Group fact this is
        :param collection: the collection to resolve group names against
        """
        links = _group_links(obj, collection)
        with ui.row().classes("gap-1"):
            for index, (name, href) in enumerate(links):
                text = name if index == len(links) - 1 else f"{name},"
                if href:
                    ui.link(text, href, new_tab=True).classes("text-body2")
                else:
                    ui.label(text).classes("text-body2")

    def _findings_panel(self, obj: Object) -> None:
        """What is wrong with the Object or its Observations, and for an Invalid Object or Observation what it was.

        :param obj: the Object to describe
        """
        findings = self.state.data.findings.get_findings(obj)
        if not obj.valid:
            with ui.card().classes("w-full bg-red-1"):
                ui.label("Invalid: left out of the website, the lists and the statistics until it is corrected.") \
                    .classes("text-body2 text-negative")
        for finding in sorted(findings, key=lambda p: (_FINDING_ORDER.get(p.severity, 0), p.observation or 0)):
            row_classes = "items-start gap-2 no-wrap"
            if finding.severity == INFO:
                row_classes += " bg-grey-2 rounded-borders q-pa-xs"
            with ui.row().classes(row_classes):
                if finding.severity == ERROR:
                    ui.icon("error", color="negative")
                elif finding.severity == WARNING:
                    ui.icon("warning", color="warning")
                else:
                    ui.icon("info", color="grey-6")
                ui.label(_finding_text(finding)).classes("text-body2")
        if not obj.valid:
            raw = obj.record if obj.raw is None else obj.raw
            ui.code(json.dumps(raw, ensure_ascii=False, indent=2)).classes("w-full")
        if obj.invalid_observations:
            ui.label(f"Observations left out ({len(obj.invalid_observations)})").classes("text-subtitle2")
            for number, raw in obj.invalid_observations:
                with ui.expansion(f"Observation {number}", icon="error").classes("w-full"):
                    ui.code(json.dumps(raw, ensure_ascii=False, indent=2)).classes("w-full")

    def _observation_list(self, observations: list[Observation]) -> None:
        """The observations one below the other, every second one on a shaded background and a thin line between them,
        so that it is easy to see where one ends and the next begins. "When" and "who" are already fixed-width, so
        always aligned; every observation's visibility table in the list shares one magnification/filter column
        width and one result column width (see _visibility_table), so the whole heading row - optic, visibility,
        Conditions - lines up down the whole list, not just the table within one observation.

        :param observations: the observations to list, in order
        """
        entries = [_entry_fields(e) for o in observations for e in o.visibility]
        left_width = max((len(left) for left, _ in entries), default=0)
        right_width = max((len(right) for _, right in entries), default=0)
        with ui.column().classes("w-full gap-0"):
            for position, observation in enumerate(observations):
                if position:
                    ui.separator()
                with ui.column().classes("w-full gap-1 p-2 rounded").style(_SHADE if position % 2 else ""):
                    self._observation_row(observation, left_width, right_width)

    def _observation_row(self, observation: Observation, left_width: int, right_width: int) -> None:
        """One observation's heading - when, optic/visibility or "Header", its Conditions, who, all bold -
        then its descriptions, notes and media thumbnails.

        :param observation: the observation to show
        :param left_width: the visibility table's magnification/filter column width, in characters (see
            _observation_list) - 0 for a Header, which never reaches here with one anyway
        :param right_width: the visibility table's result column width, in characters (see _observation_list)
        """
        with ui.row().classes("w-full items-center gap-2 p-1 rounded"):
            ui.label(_when(observation)).classes("w-32 text-caption text-weight-bold")
            if is_header(observation):  # general information about the Object: no instrument, photograph or sketch
                ui.label("Header").classes("w-24 text-weight-bold")
            else:
                ui.label(self._optic_name(observation)).classes("w-24 text-weight-bold")
                _visibility_table(observation, left_width, right_width)
            ui.label(_conditions_text(observation)).classes("flex-grow text-body2 text-weight-bold ml-4")
            ui.label(_who(observation)).classes("w-28 text-caption text-weight-bold text-right")
        for language, text in observation.descriptions:
            with ui.row().classes("w-full items-baseline gap-2 no-wrap pl-2"):
                if language:
                    ui.badge(language).props("outline").classes("text-caption")
                ui.label(text).classes("text-caption").style("white-space: pre-line")
        if observation.notes:
            ui.label(f"Notes: {observation.notes}").classes("text-caption text-italic pl-2")
        self._media_thumbnails(observation)

    def _poll_thumbnails(self) -> None:
        """Re-checks a pending DSS image or orbit diagram against disk/the task pool (see
        _THUMBNAIL_POLL_INTERVAL) - a fetch the background pool finishes while the panel is already open
        would otherwise keep showing its spinner until the Object is re-selected, since _render_thumbnails
        is otherwise only called once, when the panel opens.
        """
        if self._shown_object is not None and self._thumbnails_pending:
            self._render_thumbnails(self._shown_object)

    def _build_lightbox(self) -> None:
        """The one dialog every thumbnail's lightbox link (see _lightbox_link) shares, so its cost does
        not grow with how many thumbnails happen to be on screen. A ui.dialog is already dismissible by
        clicking outside it or pressing Escape; the explicit close button is for discoverability, same as
        the zoom toggle next to it (see _toggle_lightbox_zoom).

        The image itself is a raw ``<img>`` written through ui.html, not ui.image: ui.image wraps
        Quasar's QImg, whose outer .q-img container is only ever given a height by an explicit `ratio`
        or `height` prop - neither of which this lightbox can supply up front, since the image is an
        arbitrary one picked at click time. Without either, .q-img renders at zero height: the dialog's
        backdrop shows, but no image does. A plain <img> has none of that - it sizes itself from its own
        content exactly like the website's own lightbox already relies on.
        """
        self._lightbox_zoomed = False
        self._lightbox_url = ""
        with ui.dialog() as self._lightbox, ui.card().classes("p-0 gap-0").style(
            "max-width: 95vw; max-height: 95vh; overflow: auto;"
        ):
            with ui.row().classes("absolute top-0 right-0 z-10 gap-1 p-1"):
                ui.button(icon="zoom_out_map", on_click=self._toggle_lightbox_zoom) \
                    .props("flat round dense").tooltip("Actual size / fit to screen")
                ui.button(icon="close", on_click=self._lightbox.close).props("flat round dense")
            # sanitize=False: the only variable part is self._lightbox_url, html.escape()'d in
            # _set_lightbox_image - nothing user-supplied ever reaches this unescaped, and the default
            # client-side sanitizer cannot be relied on to keep the style attribute this needs
            self._lightbox_image = ui.html(sanitize=False).classes("contents")

    def _lightbox_link(self, url: str) -> ui.link:
        """A ui.link(target=url, new_tab=True) whose plain click shows `url` in the shared lightbox
        instead - see _LIGHTBOX_CLICK_JS and _open_lightbox. A modified click (the middle button, Ctrl,
        Cmd, Shift or Alt) still opens a real new tab, exactly as every such link already did before the
        lightbox existed.

        :param url: the full-size image to link to
        :returns: the link, as a context manager for its own ui.image child
        """
        link = ui.link(target=url, new_tab=True)
        link.on("click", self._open_lightbox, js_handler=_LIGHTBOX_CLICK_JS)
        return link

    def _set_lightbox_image(self, style: str) -> None:
        """Writes self._lightbox_image's own <img src="self._lightbox_url"> with `style`.

        :param style: the CSS to give the <img> - see _LIGHTBOX_FIT_STYLE/_LIGHTBOX_ZOOM_STYLE
        """
        url = html.escape(self._lightbox_url, quote=True)
        self._lightbox_image.set_content(f'<img src="{url}" style="{style}">')

    def _open_lightbox(self, event) -> None:
        """Shows `event.args` (the clicked link's own href, emitted by _LIGHTBOX_CLICK_JS) in the shared
        lightbox, always starting fit-to-screen - a previous image's zoom is never carried over to the
        next one."""
        self._lightbox_zoomed = False
        self._lightbox_url = event.args
        self._set_lightbox_image(_LIGHTBOX_FIT_STYLE)
        self._lightbox.open()

    def _toggle_lightbox_zoom(self) -> None:
        """Switches the lightbox image between scaled-to-fit (the default) and its real size, the card
        around it scrolling to match when that no longer fits the screen."""
        self._lightbox_zoomed = not self._lightbox_zoomed
        self._set_lightbox_image(_LIGHTBOX_ZOOM_STYLE if self._lightbox_zoomed else _LIGHTBOX_FIT_STYLE)

    def _render_thumbnails(self, obj: Object) -> None:
        """Fills self._thumbnail_container with the DSS image and any orbit diagrams, each shown once fetched
        or generated, a spinner while still pending. Sets self._thumbnails_pending so the poller knows whether
        to call this again. Rebuilds the container only when what it should show has actually changed since
        the last call (self._thumbnail_signature) - _poll_thumbnails calls this every tick while something is
        pending, and clearing/recreating a still-pending spinner every tick would restart its CSS animation,
        a visible stutter for no reason. The DSS image shows its (shared, 200x200) thumbnail but still links
        to the full-size original; an orbit diagram has no separate thumbnail, so it links to itself.

        :param obj: the Object whose thumbnails to show
        """
        assert self._thumbnail_container is not None  # set together with _shown_object, just before this is called
        dss_thumb, dss_url, dss_pending, dss_label = get_dss_status(self.state, obj)
        images = [(dss_thumb, dss_url, dss_label, dss_pending)]
        images += [(url, url, label, pending) for url, pending, label in get_orbit_status(self.state, obj)]
        shown = [(thumb, url, label) for thumb, url, label, _pending in images if url]
        pending = [label for _thumb, _url, label, pending in images if pending]
        self._thumbnails_pending = bool(pending)
        signature = (tuple(shown), tuple(pending))
        if signature == self._thumbnail_signature:
            return
        self._thumbnail_signature = signature
        self._thumbnail_container.clear()
        if not shown and not pending:
            return
        with self._thumbnail_container, ui.row().classes("gap-3 items-end pb-2"):
            for thumb, url, label in shown:
                with ui.column().classes("gap-0"):
                    with self._lightbox_link(url):
                        ui.image(thumb).classes("w-40 rounded")
                    ui.label(label).classes("text-caption")
            for label in pending:
                ui.spinner(size="lg").classes("q-mb-md")
                ui.label(f"{label} loading…").classes("text-caption")

    def _media_thumbnails(self, observation: Observation) -> None:
        """The observation's own sketch/photograph/image thumbnails, each linking to the original.

        :param observation: the observation whose media to show
        """
        urls = [*get_media_urls(observation, ObservationAttribute.SKETCH),
                *get_media_urls(observation, ObservationAttribute.PHOTOGRAPH),
                *get_media_urls(observation, ObservationAttribute.IMAGE)]
        if not urls:
            return
        with ui.row().classes("gap-2 pl-2"):
            for url in urls:
                with self._lightbox_link(url):
                    ui.image(url).classes(_THUMBNAIL_CLASSES)

    def _optic_name(self, observation: Observation) -> str:
        if observation.optic is None:
            return "—"
        if observation.project_only:
            return observation.optic.code
        return self.state.optic_names.get(observation.optic.code, observation.optic.code)

    def _show_session(self, session: Session) -> None:
        """Replaces the detail panel with this Session's own details and the Objects observed in it.

        :param session: the Session to show
        """
        self._shown_object = None
        self._thumbnail_container = None
        self._thumbnail_signature = None
        self.detail.clear()
        with self.detail:
            ui.label(_session_key(session)).classes("text-h6")
            ui.label(f"{session.start:%Y-%m-%d %H:%M} – {session.end:%H:%M}").classes("text-caption")
            ui.label(f"{session.location.name} ({session.location.latitude}, {session.location.longitude}, "
                     f"{session.location.height} m)").classes("text-caption")
            if session.conditions:
                ui.label(", ".join(f"{k}: {v}" for k, v in session.conditions.items())).classes("text-caption")
            if session.record.get(SessionAttribute.EQUIPMENT):
                ui.label(f"Equipment: {session.record[SessionAttribute.EQUIPMENT]}").classes("text-caption")
            if session.record.get(SessionAttribute.DESCRIPTION):
                ui.label(session.record[SessionAttribute.DESCRIPTION]).classes("text-body2")
            ui.separator()
            spec = FilterSpec.from_dict({"session": [_session_key(session)]})
            matches = filter_objects(self.state.data.collection, spec, self.state.data.references,
                                     self.state.data.observers)
            ui.label(f"Objects observed ({len(matches)})").classes("text-subtitle2")
            for match in matches:
                label = match.object.display_name
                ui.button(label, on_click=lambda _, o=match.object: self._show_object(o)) \
                    .props("flat dense no-caps align=left").classes("text-primary")

    # ---- reload -------------------------------------------------------------

    def _on_reloaded(self) -> None:
        """The header has already reloaded self.state (with a progress bar); rebuild this page. A session that
        was selected before the reload is looked up again by its start time (_session_key, the same identity
        the filter spec's "session" criterion uses) and put back exactly as if its row had just been clicked -
        highlighted, filtered to and shown in the detail panel - so adding observations to a session one at a
        time does not mean re-selecting it after every Reload. A session no longer found this way (deleted, or
        its start time edited) just leaves the selection cleared, as before."""
        previous_key = _session_key(self.selected_session) if self.selected_session is not None else None
        self.selected_session = None
        self.objects_table.selected = []
        self._refresh_sessions()
        self._render_finding_summary()
        if previous_key is not None:
            self.selected_session = _find_session_by_key(self._sessions_by_id.values(), previous_key)
        if self.selected_session is not None:
            row = next(r for r in self.sessions_table.rows if r["id"] == id(self.selected_session))
            self.sessions_table.selected = [row]
            self._show_session(self.selected_session)
        else:
            self.sessions_table.selected = []
            self._shown_object = None
            self._thumbnail_container = None
            self._thumbnail_signature = None
            self.detail.clear()
            with self.detail:
                ui.label("Select an object or a session to see its details.").classes("text-caption")
        self._render_session_banner()
        self._apply_filter()


# the findings panel and the "!" column both order by severity, error first; the column's sortable
# field also needs the reverse direction (most severe highest) so a click on the header brings errors up
_FINDING_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}
_FINDING_RANK = {ERROR: 3, WARNING: 2, INFO: 1}


def _finding_text(finding: Finding) -> str:
    where = f"observation {finding.observation}: " if finding.observation else ""
    return f"{where}{finding.attribute + ': ' if finding.attribute else ''}{finding.message}"


def _finding_columns(obj: Object, findings: FindingIndex) -> dict:
    """The marker of an Object in the list: `finding` is "error", "warning", "info" or "" and `finding_text` what
    a tooltip says. An Invalid Object always has an error.

    :param obj: the Object to describe
    :param findings: the findings to look it up in
    :returns: {"finding", "finding_rank", "finding_text"}
    """
    found = sorted(findings.get_findings(obj), key=lambda p: _FINDING_ORDER.get(p.severity, 0))
    severity = findings.severity(obj)
    lines = [_finding_text(p) for p in found[:3]] + ([f"(and {len(found) - 3} more)"] if len(found) > 3 else [])
    if not obj.valid:
        lines.insert(0, "Invalid")
    return {"finding": severity or "", "finding_rank": _FINDING_RANK.get(severity, 0),
            "finding_text": "\n".join(lines)}


def _notes_columns(obj: Object) -> dict:
    """The marker of an Object carrying a personal NOTES remark - an own-catalogue convention (for example
    "observe again with a different optic"), but shown for any Object that has one, whatever its catalogue.

    :param obj: the Object to describe
    :returns: {"has_notes", "notes_text"}
    """
    notes = str(obj.record.get(ObjectAttribute.NOTES, "")).strip()
    return {"has_notes": bool(notes), "notes_text": notes}


def _earliest_in_session(match, session: Session) -> datetime:
    """The earliest time `match` was observed within `session`, for sorting the Objects table by it when
    the session is selected: a community observation has no own start (dated by its Session only, see
    Observation.start), so it falls back to the session's own start.

    :param match: the Match to find a sort key for
    :param session: the selected Session, which `match.observations` is already filtered down to
    :returns: the earliest of its matched observations' start, or the session's start
    """
    return min((f.observation.start or session.start for f in match.observations), default=session.start)


def _invalid_row(obj: Object, findings: FindingIndex) -> dict:
    return {
        "id": id(obj),
        "names": obj.display_name,
        "component": component_name(obj),
        "catalogue": obj.catalogue,
        "types": ", ".join(t.value for t in obj.types),
        "constellation": obj.constellation,
        "magnitude": "—",
        "size": "—",
        "observations": _count(list(obj.observations)),
        "color": None,
        **_finding_columns(obj, findings),
        **_notes_columns(obj),
        # an Invalid Object takes part in nothing else (see CONTEXT.md), so not in this either
        "is_group": False, "group_rank": 0, "group_tooltip": "", "members": [],
        "has_references": False, "reference_rank": 0, "reference_tooltip": "", "references": [], "ref_expand": False,
    }


def _object_row(match, collection: Collection, references: References, findings: FindingIndex) -> dict:
    obj = match.object
    return {
        "id": id(obj),
        "names": obj.display_name,
        "component": component_name(obj),
        "catalogue": obj.catalogue,
        "types": ", ".join(t.value for t in obj.types),
        "constellation": obj.constellation,
        "magnitude": get_magnitude(obj, references),
        "size": _size_or_separation(obj, references),
        "observations": _count([f.observation for f in match.observations]),
        "color": _object_grade_color(obj),
        **_finding_columns(obj, findings),
        **_notes_columns(obj),
        **_group_columns(obj, collection, references, findings),
        **_reference_columns(obj, references, findings),
    }


def _group_links(obj: Object, collection: Collection) -> list[tuple[str, str]]:
    """The names of the Group fact (see ui/facts.py: object_facts), each paired with the address of the Group
    Object it names - empty when the name is a Group name with no Group Object of its own, or with more than
    one in `obj`'s own catalogue (too ambiguous to pick).

    :param obj: the Object whose Group fact this is
    :param collection: the collection to resolve group names against
    :returns: (name, link or "") pairs
    """
    names = split_names(str(obj.record.get(ObjectAttribute.GROUP, ""))) or list(obj.groups)
    links = []
    for name in names:
        matches = collection.groups_named(obj.rank, name)
        links.append((name, object_link(matches[0]) if len(matches) == 1 else ""))
    return links


def _group_columns(obj: Object, collection: Collection, references: References, findings: FindingIndex) -> dict:
    """The marker and, when there is something to expand, the members of a Group row - empty for anything
    that is not itself a Group (see Object.is_group and Collection.members_of).

    :param obj: the Object to describe
    :param collection: the collection to find members in
    :param references: the references each member row needs (see _member_row)
    :param findings: the findings each member row needs (see _member_row)
    :returns: {"is_group", "group_rank", "group_tooltip", "members"}
    """
    members = [_member_row(m, references, findings) for m in collection.members_of(obj)]
    if not obj.is_group:
        return {"is_group": False, "group_rank": 0, "group_tooltip": "", "members": []}
    tooltip = f"Group of {len(members)} member(s) — click to expand" if members else "Group with no known member"
    return {"is_group": True, "group_rank": 1, "group_tooltip": tooltip, "members": members}


def _reference_columns(obj: Object, references: References, findings: FindingIndex) -> dict:
    """The marker and, when there is something to expand, the References of a row - the other Catalogues'
    Objects that stand for the same thing (see References.of). Independent of Group membership: a row may be
    a Group, have References, both or neither.

    :param obj: the Object to describe
    :param references: the references to look it up in
    :param findings: the findings each reference row needs (see _member_row)
    :returns: {"has_references", "reference_rank", "reference_tooltip", "references", "ref_expand"}
    """
    found = [_member_row(r, references, findings) for r in references.of(obj)]
    if not found:
        return {"has_references": False, "reference_rank": 0, "reference_tooltip": "", "references": [],
                "ref_expand": False}
    tooltip = f"{len(found)} reference(s) — click to expand"
    return {"has_references": True, "reference_rank": 1, "reference_tooltip": tooltip, "references": found,
            "ref_expand": False}


def _member_row(obj: Object, references: References, findings: FindingIndex) -> dict:
    """One row of an expanded Group - the same columns as an Object row (_object_row), so the member rows line
    up under the table's own columns instead of being a block of plain text. The observation count is the
    member's own, not filtered by whatever the active search matched: a Group's membership does not depend on
    it. The Component (blank when the record does not give one, like the table's own column) is what actually
    tells the members of one group apart from each other.

    :param obj: the member Object to describe
    :param references: for resolving magnitude/separation through a reference
    :param findings: for the row's finding marker
    :returns: the row, in the same shape as _object_row
    """
    return {
        "id": id(obj),
        "names": obj.display_name,
        "component": component_name(obj),
        "catalogue": obj.catalogue,
        "types": ", ".join(t.value for t in obj.types),
        "constellation": obj.constellation,
        "magnitude": get_magnitude(obj, references),
        "size": _size_or_separation(obj, references),
        "observations": _count(list(obj.all_observations)),
        "color": _object_grade_color(obj),
        **_finding_columns(obj, findings),
        **_notes_columns(obj),
    }


def get_magnitude(obj: Object, references: References) -> str:
    """The visual magnitude ("v...") when there is one; the blue/photographic one ("b...", never the
    "bv..." color index) otherwise; the first value as a last resort (for example a GCVS "p..." one).
    A double star has one such value per component, separated by ";" in the record; the same rule
    picks each component's value, and the two are shown separated by " / ". The own catalogue's double
    stars usually carry no MAGNITUDE themselves, so this reads it through the reference (in practice
    the WDS pair) when the object itself has none - see References.resolved.

    :param obj: the Object to describe
    :param references: for resolving the value through a reference
    :returns: the formatted magnitude, or "—" when there is none
    """
    raw = references.resolved(obj, ObjectAttribute.MAGNITUDE)
    if not raw:
        return "—"
    if ObjectType.DOUBLE_STAR in obj.types:
        return " / ".join(_pick_magnitude(component) for component in raw.split(";"))
    return _pick_magnitude(raw)


def _pick_magnitude(raw: str) -> str:
    """One component's value from a comma-separated MAGNITUDE field: visual ("v...") first, then blue/
    photographic ("b...", never "bv..."), then whatever is first.

    :param raw: one component's raw, comma-separated MAGNITUDE value
    :returns: the picked value, or "—" when there is none
    """
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return "—"
    visual = next((p for p in parts if p.startswith("v")), None)
    if visual:
        return visual
    blue = next((p for p in parts if p.startswith("b") and not p.startswith("bv")), None)
    return blue or parts[0]


def _size_or_separation(obj: Object, references: References) -> str:
    """A double star's separation, read through the reference when the own catalogue's pair (usually)
    does not carry one itself - see References.resolved_separation; SIZE for anything else, as
    "major' x minor'" - SIZE is already in arcminutes, minor may be absent. Neither shows the
    position angle - not needed for a double star, so dropped here too for consistency.

    :param obj: the Object to describe
    :param references: for resolving a double star's separation through a reference
    :returns: the formatted size or separation, or "—" when there is none
    """
    if ObjectType.DOUBLE_STAR in obj.types:
        separation = references.resolved_separation(obj)
        return f'{separation}"' if separation else "—"
    raw = obj.record.get(ObjectAttribute.SIZE)
    parts = str(raw).split(",") if raw else []
    major = parts[0] if parts and parts[0] else None
    if not major:
        return "—"
    text = f"{major}'"
    if len(parts) > 1 and parts[1]:
        text += f" x {parts[1]}'"
    return text


_GRADE_COLOR_RANK = {"green": 0, "orange": 1, "blue": 2, "red": 3}  # best to worst, as the old app ranked them


def _object_grade_color(obj: Object) -> str | None:
    """Text color by the best private Grade, the same scheme the old app used: green for an easy
    grade, orange for a harder one, red for failed, blue for observed with no Grade at all (bright
    objects such as the Moon carry none); None when there is no private observation at all.

    :param obj: the Object to describe
    :returns: the color, or None when there is no private observation
    """
    double_star = ObjectType.DOUBLE_STAR in obj.types
    best: str | None = None
    for observation in obj.observations:
        if observation.public:
            continue
        bucket = None
        for entry in observation.visibility:
            if not isinstance(entry.result, Grade):
                continue
            candidate = _grade_bucket(entry.result.low, double_star)
            if bucket is None or _GRADE_COLOR_RANK[candidate] < _GRADE_COLOR_RANK[bucket]:
                bucket = candidate
        bucket = bucket or "blue"  # observed, but no Grade in any entry
        if best is None or _GRADE_COLOR_RANK[bucket] < _GRADE_COLOR_RANK[best]:
            best = bucket
    return best


def _grade_bucket(value: float, double_star: bool) -> str:
    """The color bucket ("green"/"orange"/"red") a Grade value falls into; the thresholds differ for a
    double star, whose scale runs tighter.

    :param value: the low end of the Grade's range
    :param double_star: whether the Object is a double star
    :returns: the color bucket
    """
    if double_star:
        return "green" if value <= 1 else "orange" if value <= 2 else "red"
    return "green" if value <= 3 else "orange" if value <= 5 else "red"


def _session_object_counts(collection: Collection) -> dict[int, int]:
    """The number of distinct Objects with an observation in each Session, in one pass over the
    collection rather than one filter_objects call per session (real data has hundreds of sessions
    and tens of thousands of objects, so a call per session does not scale).

    :param collection: the collection to scan
    :returns: id(Session) -> the number of distinct Objects observed in it
    """
    per_session: dict[int, set[int]] = {}
    for obj in collection.objects:
        for observation in obj.all_observations:
            if observation.session is not None:
                per_session.setdefault(id(observation.session), set()).add(id(obj))
    return {session_id: len(object_ids) for session_id, object_ids in per_session.items()}


def _session_row(session: Session, object_count: int) -> dict:
    same_day = session.end.date() == session.start.date()
    date_text = session.start.date().isoformat()
    if not same_day:
        date_text += f" – {session.end.date().isoformat()}"
    return {
        "id": id(session),
        "date": date_text,
        "time": f"{session.start:%H:%M} – {session.end:%H:%M}",
        "location": session.location.name,
        "bortle": session.conditions.get(ConditionAttribute.BORTLE, ""),
        "nelm": session.conditions.get(ConditionAttribute.NELM, ""),
        "sqm": session.conditions.get(ConditionAttribute.SQM, ""),
        "sqml": session.conditions.get(ConditionAttribute.SQML, ""),
        "seeing": session.conditions.get(ConditionAttribute.SEEING, ""),
        "objects": object_count,
        "color": _session_bortle_color(session),
    }


def _session_bortle_color(session: Session) -> str | None:
    """Text color by Bortle class, the same scheme the old app used: green for a dark sky (1-4),
    orange for 5-6, red for a bright sky (7-9); None when no Bortle reading was given.

    :param session: the Session to describe
    :returns: the color, or None when there is no Bortle reading
    """
    bortle = session.conditions.get(ConditionAttribute.BORTLE, "")
    if re.search(r"[789]", bortle):
        return "red"
    if re.search(r"[56]", bortle):
        return "orange"
    if re.search(r"[1234]", bortle):
        return "green"
    return None


def _count(observations: list[Observation]) -> int:
    """How many of the observations are observations: the Header, general information about the Object, is not.

    :param observations: the observations to count
    :returns: the count
    """
    return sum(1 for observation in observations if not is_header(observation))


def _grouped_observations(observations: list[Observation]) -> list[tuple[str, list[Observation]]]:
    """Own (public), Own (private), then one group per community observer, name-sorted. Groups with
    nothing in them are left out.

    :param observations: the observations to group
    :returns: (group label, its observations) pairs
    """
    own_public = [o for o in observations if o.observer is None and o.public]
    own_private = [o for o in observations if o.observer is None and not o.public]
    by_observer: dict[str, list[Observation]] = {}
    for observation in observations:
        if observation.observer is not None:
            by_observer.setdefault(observation.observer.name, []).append(observation)

    groups: list[tuple[str, list[Observation]]] = []
    if own_public:
        groups.append(("Own (public)", own_public))
    if own_private:
        groups.append(("Own (private)", own_private))
    groups.extend((name, by_observer[name]) for name in sorted(by_observer))
    return groups


def _canonical_constellation(value: str) -> str:
    """The IAU abbreviation of `value`, whatever case it is written in - so the Constellation filter's options
    don't show "And" and "AND" as two different choices (a stale conversion of a catalogue can still have the
    old, wrongly-cased values; matching itself is already case-insensitive, see FilterSpec, so this only
    affects what the dropdown offers). A value that names none of the 88 IAU constellations - CONSTELLATION is
    free text, not validated against that list - is shown as written rather than dropped.

    :param value: the raw CONSTELLATION value
    :returns: the canonical abbreviation, or `value` itself when it names no IAU constellation
    """
    try:
        return constellation_name(value)
    except ValueError:
        return value


class _HasObjects(Protocol):  # pylint: disable=too-few-public-methods
    """Anything with the one attribute `_observer_options` actually needs - a real Collection, or a
    test double standing in for one. A property, not a plain attribute, so a read-only `Sequence` is
    enough - `_observer_options` never writes it, unlike Collection's own mutable `list`."""
    @property
    def objects(self) -> Sequence[Object]:
        ...


class _HasCatalogues(Protocol):  # pylint: disable=too-few-public-methods
    """Anything with the one attribute `_default_catalogues` and `_default_observers` need - a real
    Collection, or a test double standing in for one."""
    @property
    def catalogues(self) -> Sequence[Catalogue]:
        ...


def _default_catalogues(collection: _HasCatalogues) -> list[str]:
    """The Catalogue filter's default: the own catalogue plus the WDS, when more than one catalogue is
    loaded. A double star's own observations live on its WDS pair/Group, not on an own-catalogue
    Object of its own (see CONTEXT.md "Own catalogue") - without the WDS selected too, the table
    would never show a double star at all. Joining every catalogue by default (e.g. the UGC or GCVS too)
    would make the initial table both huge and not what you usually want.

    :param collection: the collection to default from
    :returns: the catalogue names to default to, or [] when there is only one (nothing to narrow)
    """
    catalogues = collection.catalogues
    if len(catalogues) <= 1:
        return []
    own_name = catalogues[0].name
    return [c.name for c in catalogues if c.name == own_name or c.name.casefold() == "wds.json"]


def _default_observers(collection: _HasCatalogues, observers: Observers | None, options: dict[str, str]) -> list[str]:
    """The Observer filter's default: the owner, but only together with the Catalogue default above (same
    guard) - otherwise the WDS catalogue's own ~170k objects would show by default. Moot once a session
    is selected, which already narrows to the owner's own observations on its own.

    :param collection: the collection the Catalogue default is computed from
    :param observers: the observers, to resolve the owner's id
    :param options: the Observer dropdown's own options (see _observer_options), to check the owner is
        actually one of them (nothing to filter for otherwise)
    :returns: [owner id], or [] when there is nothing to narrow or no owner option to select
    """
    if not _default_catalogues(collection):
        return []
    owner_id = observers.owner_id() if observers else OWN_ID
    return [owner_id] if owner_id in options else []


def _observer_options(collection: _HasObjects, observers: Observers | None) -> dict[str, str]:
    """Observer id -> "Firstname Surname (id)", for every observer with at least one attached
    observation: the owner first, then the observers with scope GLOBAL, then (after a separator)
    every scope PROJECT observer -- each tier sorted by name. The scope comes from the Observer
    itself (set when the observers file was loaded), never a name hardcoded here.

    An own-catalogue observation never carries an Observer (see Observation.observer) even though it
    is the owner's - so unlike every other observer, whose only way in is an attached Observation, the
    registered OWNER-scope observer is added explicitly whenever there is at least one own observation
    anywhere, whether or not the owner also happens to have a community-imported one (such as a
    project CSV submission).

    :param collection: the collection to scan for attached observations
    :param observers: the observers, for finding the owner
    :returns: observer id -> its dropdown label, in display order (a "" key is the tier separator)
    """
    by_id = {o.observer.id: o.observer for obj in collection.objects for o in obj.all_observations if o.observer}
    if (observers is not None and observers.owner is not None and observers.owner.id not in by_id
            and any(o.observer is None for obj in collection.objects for o in obj.all_observations)):
        by_id[observers.owner.id] = observers.owner
    tiers: dict[Scope, list[Observer]] = {Scope.OWNER: [], Scope.GLOBAL: [], Scope.PROJECT: []}
    for observer in by_id.values():
        tiers[observer.scope].append(observer)
    for tier in tiers.values():
        tier.sort(key=lambda o: o.name.casefold())

    options: dict[str, str] = {}
    for observer in (*tiers[Scope.OWNER], *tiers[Scope.GLOBAL]):
        options[observer.id] = f"{observer.name} ({observer.id})"
    if options and tiers[Scope.PROJECT]:
        options[""] = "──── project observers ────"
    for observer in tiers[Scope.PROJECT]:
        options[observer.id] = f"{observer.name} ({observer.id})"
    return options


def _session_key(session: Session) -> str:
    return session.start.isoformat(timespec="minutes")


def _find_session_by_key(sessions: Iterable[Session], key: str) -> Session | None:
    """The Session among `sessions` whose `_session_key` matches `key`, or None - a Reload replaces every
    Session object, so BrowsePage._on_reloaded looks the previously-selected one up again this way.

    :param sessions: the sessions to search
    :param key: the key to match, as _session_key gives it
    :returns: the matching Session, or None
    """
    return next((s for s in sessions if _session_key(s) == key), None)


def _when(observation: Observation) -> str:
    if observation.start is None:
        return "public"
    if observation.end and observation.end != observation.start:
        return f"{observation.start:%Y-%m-%d %H:%M}–{observation.end:%H:%M}"
    return f"{observation.start:%Y-%m-%d %H:%M}"


def _who(observation: Observation) -> str:
    return observation.observer.name if observation.observer else "you"


def _visibility_table(observation: Observation, left_width: int, right_width: int) -> None:
    """The observation's visibility entries, one below the other, as two aligned columns: the magnification
    and filter on the left, the Grade range or other result on the right. A real CSS grid (rather than
    padding with spaces, which a browser's proportional font would not line up) keeps the two columns
    aligned; both column widths are given in characters rather than computed from this observation's own
    entries alone (`max-content` would), so that every observation in the same list (see _observation_list)
    shares them and the whole heading row - not just the table - lines up down the whole list.

    :param observation: the observation whose visibility entries to show
    :param left_width: the left column's width, in characters
    :param right_width: the right column's width, in characters
    """
    rows = [_entry_fields(e) for e in observation.visibility] or [("", "")]
    with ui.element("div").classes("gap-x-2 gap-y-0").style(
            f"display: grid; grid-template-columns: {left_width}ch {right_width}ch; align-items: baseline;"):
        for left, right in rows:
            ui.label(left).classes("text-body2 text-weight-bold")
            ui.label(right).classes("text-body2 text-weight-bold")


def _entry_fields(entry: VisibilityEntry) -> tuple[str, str]:
    """One visibility entry as (left, right) cells: the magnification and filter (e.g. "37x + UHC") on the
    left, its result on the right - a Grade range in parentheses (e.g. "(2)", a private observation only),
    or a Difficulty/Color plain, with no parentheses (a public observation only).

    :param entry: the entry to format
    :returns: the (left, right) cell texts
    """
    if isinstance(entry.result, Grade):
        text = f"{entry.result.low:g}"
        if entry.result.high != entry.result.low:
            text += f"-{entry.result.high:g}"
        text = f"({text})"
    elif entry.result is not None:
        text = entry.result.value
    else:
        text = ""
    left = f"{entry.magnification}x" if entry.magnification else ""
    if entry.filter:
        left = f"{left} + {entry.filter}" if left else entry.filter
    return left, text


_CONDITION_LABEL = {
    ConditionAttribute.BORTLE: "Bortle", ConditionAttribute.NELM: "NELM", ConditionAttribute.SQM: "SQM",
    ConditionAttribute.SQML: "SQM-L", ConditionAttribute.SEEING: "Seeing",
}
_LOCAL_FOR = {
    ConditionAttribute.NELM: ConditionAttribute.NELM_LOCAL, ConditionAttribute.SQML: ConditionAttribute.SQML_LOCAL,
    ConditionAttribute.SEEING: ConditionAttribute.SEEING_LOCAL,
}


def _conditions_text(observation: Observation) -> str:
    """All of an observation's Conditions (see CONTEXT.md): the general readings - from its Session for a
    private observation, from the observation's own record otherwise, since a public or community
    observation carries them directly - each immediately followed, in parentheses, by its Local reading
    near the object when the observation gives one (Bortle has no local counterpart).

    :param observation: the observation to read
    :returns: the formatted conditions, or "" when it has none
    """
    general = observation.session.conditions if observation.session else observation.record
    parts = []
    for key in CONDITION_ATTRIBUTES:
        value, local_key = general.get(key), _LOCAL_FOR.get(key)
        local_value = observation.record.get(local_key) if local_key else None
        if not value and not local_value:
            continue
        label = _CONDITION_LABEL[key]
        if value and local_value:
            parts.append(f"{label} {value} ({local_value})")
        elif value:
            parts.append(f"{label} {value}")
        else:
            parts.append(f"{label} ({local_value})")
    return ", ".join(parts)
