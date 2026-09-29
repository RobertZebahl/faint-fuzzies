"""The header shared by every page: title, navigation between pages, and the Reload action - with a
progress bar that has two sources, never shown at once. While a Reload runs, it shows the reload's own
step and fraction. The rest of the time, the bar itself reflects the background DSS/orbit TaskPool's
overall progress (done/total across every category, summed - see tasks.py), hidden when there is nothing
left in the batch, while the text in front breaks that same total down per category, each with its own verb
("Fetching DSS images (5/200), generating orbit diagrams (3/140)…"), leaving out a category with nothing to
do. A Reload re-seeds the pool as part of
loading (see AppState._refresh_media_tasks), so the moment a Reload finishes, the bar has already fallen
back to showing that fresh batch's progress, without any special handling here - the same poll just starts
reading from the other source again.

The reload itself runs in a worker thread (nicegui.run.io_bound) so the page stays responsive while it
works. That thread must never touch a UI element directly - NiceGUI element updates are for the client's
own event-loop thread only. So the reload's progress callback (called from the worker thread) just writes
into a plain dict, and one ui.timer (running on the page, i.e. the right thread), started once and never
stopped, polls either that dict or the thread-safe TaskPool and updates the progress bar and label.
"""
from collections.abc import Callable

from nicegui import run, ui

from faint_fuzzies.media_pool import DSS_CATEGORY, ORBIT_CATEGORY
from faint_fuzzies.ui.state import AppState

# DSS images are fetched (from the ESO archive); orbit diagrams are generated (from orbital elements) -
# different verbs, since they are different kinds of work, not just different subjects
_CATEGORY_PHRASES = {DSS_CATEGORY: "fetching DSS images", ORBIT_CATEGORY: "generating orbit diagrams"}

PAGES = (("browse", "Browse", "/"), ("site", "Site", "/site"), ("statistics", "Statistics", "/statistics"),
        ("log", "Log", "/log"))
POLL_INTERVAL = 0.2


def header(active: str, state: AppState, on_reloaded: Callable[[], None]) -> None:
    """Builds the page header: title, navigation links, the Reload button, and the progress bar/label
    described in the module docstring.

    :param active: the name of the current page, bold in the navigation links
    :param state: the app's shared state; Reload re-reads the data directory through it
    :param on_reloaded: called after a Reload finishes, so the page can refresh what it shows
    """
    with ui.header().classes("items-center"):
        ui.label("Faint Fuzzies").classes("text-h6")
        for name, label, path in PAGES:
            classes = "text-white" + (" text-weight-bold" if name == active else "")
            ui.link(label, path).classes(classes).style("text-decoration: none")
        ui.space()
        status = ui.label("").classes("text-caption text-white")
        # white on the fill, grey on the track: the header itself is the primary color, so a
        # progress bar left at its own default (also primary) would be invisible against it.
        # instant-feedback: Quasar otherwise animates value changes over a short transition, so the
        # status label (which changes instantly) could show "Done" while the bar visually still shows
        # an earlier, lower value it hasn't finished catching up to.
        progress = ui.linear_progress(value=0, show_value=False, color="white") \
            .classes("w-32").props("track-color=grey-4 rounded instant-feedback")
        progress.visible = False
        button = ui.button("Reload", icon="refresh").mark("reload-button")

        reload_progress = {"active": False, "step": "", "fraction": 0.0}

        def poll() -> None:  # runs on the page's own thread, safe to touch the UI
            if reload_progress["active"]:
                status.text = reload_progress["step"]
                progress.value = reload_progress["fraction"]
                progress.visible = True
                return
            by_category = state.task_pool.progress()
            total_done = sum(done for done, _ in by_category.values())
            total = sum(count for _, count in by_category.values())
            if total == 0 or total_done >= total:
                status.text = ""
                progress.visible = False
                return
            parts = (f"{_CATEGORY_PHRASES.get(category, category)} ({done}/{count})"
                    for category, (done, count) in by_category.items())
            text = ", ".join(parts) + "…"
            status.text = text[0].upper() + text[1:]
            progress.value = total_done / total
            progress.visible = True

        ui.timer(POLL_INTERVAL, poll)

        async def reload() -> None:
            button.disable()
            reload_progress.update(active=True, step="Starting…", fraction=0.0)

            def report(step: str, fraction: float) -> None:  # runs on the worker thread
                reload_progress["step"], reload_progress["fraction"] = step, fraction

            try:
                await run.io_bound(state.reload, report)
            finally:
                reload_progress["active"] = False
                button.enable()
            on_reloaded()
            ui.notify("Reloaded from disk.", type="positive")

        button.on_click(reload)
