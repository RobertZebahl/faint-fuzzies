"""The Site page: builds the static website (see site/build.py, site/output.py) from the data the app already
has loaded, into `data_dir/site-build/` - a generated, disposable folder, like `dss/` and `orbits/` (see
media_pool.site_build_dir) - then serves it locally through a PHP dev server the app spawns itself, and can
upload it to its host (see upload.py).

"Build", with "Fetch/Generate missing images" checked (the default), first waits for the background task pool
(see tasks.py) to finish everything it currently has queued, then builds; unchecked, it builds immediately with
whatever DSS images and orbit diagrams are already cached. Either way it never queues anything itself - the
pool is already seeded with every missing DSS/orbit task for the same data this builds from (see
AppState._refresh_media_tasks), so "Fetch/Generate missing images" is simply waiting for a pool that is already
working towards exactly what the site needs (DSS images are fetched, orbit diagrams are generated - hence the
name). If the app was started with `--no-dss-fetch` or `--no-orbits-generation`, that pool is deliberately
empty, so this refuses rather than building a site with gaps it never tried to fill. "Prune" is checked by
default here, unlike build-site's own opt-in `--prune`: this page's build is a disposable, generated folder with
nothing else ever writing into it (see media_pool.site_build_dir above), so nothing is normally lost by deleting
what the build no longer accounts for - see site/output.write_site. Unchecking it behaves exactly like build-site
without `--prune`: whatever an earlier build left behind simply stays.

"Upload" asks for confirmation first - unlike a build, it reaches a live host, not just this machine - then runs
the same upload `faint-fuzzies upload` does, with `--delete` and `--checksum` available here too, as two
checkboxes next to the button, both checked by default (`--dry-run` stays CLI-only: a preview run has no obvious
use from a page that always builds from the data already loaded). Checking "Delete" makes the confirmation
dialog say so explicitly, since unlike a plain upload it can remove files already on the host - the same safety
check `upload.py` always applies (refusing an empty or "/" remote_path without confirm_delete_root) still
applies here too. rsync's own output is shown live in a log box on this page (see upload.py's `on_line`), the
same lines the command line's own terminal would get.
"""
import asyncio
from typing import Any

from nicegui import run, ui

from faint_fuzzies.config import UploadConfig
from faint_fuzzies.domain.findings import CatalogueError
from faint_fuzzies.media_pool import site_build_dir
from faint_fuzzies.ui.nav import header
from faint_fuzzies.ui.state import AppState
from faint_fuzzies.upload import UploadError, upload_site

POLL_INTERVAL = 0.2


def build(state: AppState) -> None:
    """Builds the Site page.

    :param state: the app's shared state
    """
    SitePage(state)


class SitePage:
    """The Site page's controller: its NiceGUI elements and the build/upload actions behind its buttons and
    checkboxes.

    :param state: the app's shared state
    """

    def __init__(self, state: AppState) -> None:
        self.state = state
        self.output_dir = site_build_dir(state.data_dir)
        self._progress = {"active": False, "step": "", "fraction": 0.0}
        self._upload_lines: list[str] = []
        self._upload_lines_shown = 0

        header("site", state, lambda: None)
        # NiceGUI's own documented way of letting one element fill the height Quasar leaves below the
        # header: .q-page becomes a flex container (default row direction) with .nicegui-content as its
        # sole child - .q-page's default cross-axis alignment (align-items: stretch) then gives
        # .nicegui-content a real, definite height automatically, no explicit height needed or wanted
        # here: an explicit h-full would instead try to resolve "100% of .q-page" as a percentage, which
        # depends on .q-page itself having a non-auto height - it only has a min-height (Quasar's own
        # doing, to let a short page still fill the viewport while a tall one scrolls), so that percentage
        # silently resolves to nothing and overrides the stretch that would otherwise have worked. Width
        # is the opposite: it is .q-page's main axis, which is never auto-stretched, so .nicegui-content
        # does need the explicit w-full below. self.upload_log is a DIRECT child of .nicegui-content (not
        # nested inside the column below - that would reintroduce the same percentage-height problem one
        # level down) and gets flex-grow to claim whatever height .nicegui-content's own stretch leaves.
        ui.query(".q-page").classes("flex")
        ui.query(".nicegui-content").classes("w-full")
        with ui.column().classes("w-full p-4 gap-3"):
            ui.label("Site").classes("text-subtitle1")
            ui.label(f"Built into {self.output_dir}").classes("text-caption")

            # narrower than the row below (on purpose): a progress bar stretched across the full page
            # width looks wrong, unlike the row of checkboxes, which needs the width to not wrap
            with ui.column().classes("w-full max-w-3xl gap-3"):
                self.status_label = ui.label("").classes("text-caption")
                self.progress_bar = ui.linear_progress(value=0, show_value=False).classes("w-1/2").props(
                    "instant-feedback")
                self.progress_bar.visible = False

            with ui.row().classes("items-center gap-3"):
                self.build_button = ui.button("Build").mark("build-button")
                self.fetch_missing_checkbox = ui.checkbox("Fetch/Generate missing images", value=True).mark(
                    "fetch-missing-checkbox")
                self.prune_checkbox = ui.checkbox("Prune", value=True).mark("prune-checkbox")
                self.upload_button = ui.button("Upload").mark("upload-button")
                self.checksum_checkbox = ui.checkbox("Checksum (rsync)", value=True).mark(
                    "upload-checksum-checkbox")
                self.delete_checkbox = ui.checkbox("Delete (rsync)", value=True).mark("upload-delete-checkbox")

            self.link_area = ui.row().classes("items-center gap-2")
            self.report_label = ui.markdown("").mark("site-report")

        # outside the max-w-3xl column above (on purpose - rsync lines are long, unlike the labels/buttons
        # above, so this uses the page's full width, not just that narrower, centered column) and a direct
        # child of .nicegui-content, so flex-grow here claims the remaining height - see the comment above
        self.upload_log = ui.log(max_lines=500).classes("w-full flex-grow mx-4").mark("upload-log")
        self.upload_log.visible = False

        ui.timer(POLL_INTERVAL, self._poll)
        self.build_button.on_click(lambda: self._run(fetch_missing=self.fetch_missing_checkbox.value,
                                                      prune=self.prune_checkbox.value))
        self.upload_button.on_click(self._confirm_and_upload)

    def _poll(self) -> None:
        """Reflects `self._progress` and `self._upload_lines` (both written from a worker thread, by `_run`
        and `_upload` respectively) onto this page's elements; runs on the page's own thread, called by a
        ui.timer - NiceGUI elements are only ever touched from here, never from the worker thread itself."""
        if self._progress["active"]:
            self.status_label.text = self._progress["step"]
            self.progress_bar.value = self._progress["fraction"]
            self.progress_bar.visible = True
        else:
            self.progress_bar.visible = False
        while self._upload_lines_shown < len(self._upload_lines):
            self.upload_log.push(self._upload_lines[self._upload_lines_shown])
            self._upload_lines_shown += 1

    async def _run(self, fetch_missing: bool, prune: bool) -> None:
        """Handles a click of "Build": optionally waits for the task pool first, then builds the site and
        shows its report and preview link.

        :param fetch_missing: whether to wait for the background task pool to finish before building
            ("Fetch/Generate missing images" checked)
        :param prune: whether to delete anything the build no longer accounts for ("Prune" checked - see
            the module docstring)
        """
        if fetch_missing and not (self.state.fetch_dss and self.state.generate_orbits):
            ui.notify("Images are off for this session (started with --no-dss-fetch/--no-orbits-generation); "
                      "restart the app without those flags to build a complete site.", type="negative")
            return
        self.build_button.disable()
        self.fetch_missing_checkbox.disable()
        self.prune_checkbox.disable()
        self.upload_button.disable()
        self.report_label.set_content("")
        self._progress.update(active=True, step="Starting…", fraction=0.0)
        try:
            if fetch_missing:
                await self._wait_for_pool()

            def on_progress(step: str, fraction: float) -> None:
                self._progress["step"], self._progress["fraction"] = step, fraction

            report = await run.io_bound(self.state.build_site, self.output_dir, on_progress, prune)
            if report is None:  # the call was canceled, or the app is shutting down (see nicegui.run.io_bound)
                return
            self.report_label.set_content(_format_report(report))
            self.state.site_server.ensure_running(self.output_dir)
            self._show_link()
        finally:
            # cleared directly here, not left to _poll: write_site's last few steps (making the last
            # thumbnails, pruning, scanning for broken links, "Done") often finish faster than
            # POLL_INTERVAL, so _poll's last read before "active" goes False can still be an earlier
            # step - leaving it showing, say, "Rendering pages (80/80)" forever once the build is done
            self._progress["active"] = False
            self.status_label.text = ""
            self.build_button.enable()
            self.fetch_missing_checkbox.enable()
            self.prune_checkbox.enable()
            self.upload_button.enable()

    async def _wait_for_pool(self) -> None:
        """Polls the background task pool until it has nothing left queued, updating `self._progress`."""
        self._progress["step"] = "Fetching DSS images and orbit diagrams…"
        while True:
            by_category = self.state.task_pool.progress()
            total_done = sum(done for done, _ in by_category.values())
            total = sum(count for _, count in by_category.values())
            if total == 0 or total_done >= total:
                self._progress["fraction"] = 1.0
                return
            self._progress["fraction"] = total_done / total
            await asyncio.sleep(POLL_INTERVAL)

    def _show_link(self) -> None:
        """Shows the preview server's link once it is running, or its error if it failed to start."""
        server = self.state.site_server
        self.link_area.clear()
        with self.link_area:
            if server.url:
                ui.link(f"Open {server.url}", server.url, new_tab=True)
            elif server.error:
                ui.label(server.error).classes("text-negative")

    async def _confirm_and_upload(self) -> None:
        """Handles a click of "Upload": resolves the config file first (its own error, if any, needs no
        confirmation dialog), then asks for confirmation naming the real target - unlike a build, this
        reaches a live host, not just this machine - and, if "Delete" is checked, saying so explicitly,
        since that run can remove files already on the host."""
        if not self.output_dir.is_dir():
            ui.notify("Nothing built yet - use Build first.", type="negative")
            return
        from faint_fuzzies.config import resolve_upload_config
        try:
            config = resolve_upload_config()
        except CatalogueError as exc:
            ui.notify(str(exc), type="negative")
            return
        delete = self.delete_checkbox.value
        checksum = self.checksum_checkbox.value
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Upload to {config.user}@{config.host}:{config.remote_path}?")
            if delete:
                ui.label("Also deletes anything already there that is not part of this build.").classes(
                    "text-caption text-negative")
            else:
                ui.label("Adds and updates files there; nothing already on the host is removed.").classes(
                    "text-caption")
            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("Cancel", on_click=lambda: dialog.submit(False)).props("flat")
                ui.button("Upload", on_click=lambda: dialog.submit(True)).props("color=primary") \
                    .mark("confirm-upload-button")
        if await dialog:
            await self._upload(config, delete=delete, checksum=checksum)

    async def _upload(self, config: UploadConfig, delete: bool, checksum: bool) -> None:
        """Uploads the built site to `config`'s host, the same plain upload the command line does, with
        `delete`/`checksum` as the "Delete"/"Checksum" checkboxes were set (no --dry-run - see the module
        docstring), showing rsync's own output live in `self.upload_log` as it is produced (see upload.py's
        `on_line`).

        :param config: the resolved upload target
        :param delete: whether to pass rsync --delete
        :param checksum: whether to pass rsync --checksum
        """
        self.build_button.disable()
        self.fetch_missing_checkbox.disable()
        self.upload_button.disable()
        self.delete_checkbox.disable()
        self.checksum_checkbox.disable()
        self._upload_lines.clear()
        self._upload_lines_shown = 0
        self.upload_log.clear()
        self.upload_log.visible = True
        ui.notify(f"Uploading to {config.host}…")
        try:
            try:
                code = await run.io_bound(upload_site, self.output_dir, config, delete=delete, checksum=checksum,
                                          on_line=self._upload_lines.append)
            except UploadError as exc:
                ui.notify(str(exc), type="negative")
                return
            if code is None:  # the call was canceled, or the app is shutting down (see nicegui.run.io_bound)
                return
            if code == 0:
                ui.notify("Upload finished.", type="positive")
            else:
                ui.notify(f"rsync exited with code {code} - see the log above for details", type="negative")
        finally:
            self.build_button.enable()
            self.fetch_missing_checkbox.enable()
            self.upload_button.enable()
            self.delete_checkbox.enable()
            self.checksum_checkbox.enable()


def _format_report(report: dict[str, Any]) -> str:
    """The build's report, as Markdown: the summary counts as bullet points, then every non-empty category
    (missing images, overwritten images, broken links) in full, in a fenced code block - the same detail
    `build-site` itself prints to the shell, not just a 3-item teaser.

    :param report: the report returned by AppState.build_site
    :returns: the formatted report
    """
    lines = [
        f"- {report['pages']} pages written",
        f"- {report['linked']} image(s) linked, {report['copied']} copied",
        f"- {report['thumbnails']} thumbnail(s) made, {report['thumbnails_reused']} reused",
        f"- {report['pruned']} orphaned file(s) removed",
        _detail_section(report, "missing", "image(s) missing"),
        _detail_section(report, "overwritten", "image(s) overwrote a base/static file"),
        _detail_section(report, "broken_links", "broken link(s)"),
    ]
    return "\n".join(line for line in lines if line)


def _detail_section(report: dict[str, Any], key: str, noun: str) -> str:
    """One report category as a bold count followed by every example in a fenced code block, or "" when
    the category is empty - `report[f"{key}_examples"]` is already capped (20, see site/output.py), so
    "and N more" covers whatever that cap left out.

    :param report: the report returned by AppState.build_site
    :param key: the report's count key ("missing", "overwritten" or "broken_links")
    :param noun: what the count is of, for the heading
    :returns: the section's Markdown, or "" when there is nothing to show
    """
    count = report[key]
    if not count:
        return ""
    examples = report[f"{key}_examples"]
    hidden = count - len(examples)
    more = f"\n… and {hidden} more" if hidden > 0 else ""
    return f"- **{count} {noun}**:\n```\n" + "\n".join(examples) + f"{more}\n```"
