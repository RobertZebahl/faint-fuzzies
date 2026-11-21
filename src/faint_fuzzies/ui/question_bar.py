"""The Browse page's Question field (only there with an [ai] table, see ai.service): a Question asked in German or
English, the search text it comes with shown as a chip that can be edited and removed, the progress of whatever
the model server is doing, and a line for what the Question could not express or why it failed.

The page does the asking and the searching (see BrowsePage._ask and BrowsePage._search); this only shows them.
The model server's work runs in a worker thread, and its progress is read from the service by a timer here, never
pushed from that thread."""
from collections.abc import Awaitable, Callable

from nicegui import ui

from faint_fuzzies.ai.service import AiService, AiState

POLL_SECONDS = 0.5

_PLACEHOLDER = "Welche Galaxien zeigten Details mit bis zu 4 Zoll Öffnung?"


def status_text(service: AiService, busy: bool) -> str | None:
    """What the field says about the model server: its progress while it starts, indexes or works for the page,
    why it failed, or None when there is nothing to tell."""
    step, fraction = service.progress
    if busy or service.state in (AiState.STARTING, AiState.INDEXING):
        return f"{step} {fraction:.0%}" if fraction else step
    if service.state is AiState.FAILED:
        return service.message
    return None


def ignored_text(ignored: tuple[str, ...]) -> str:
    """The warning about the parts of a Question no criterion expresses."""
    return "Not expressed: " + ", ".join(f"'{part}'" for part in ignored) + " - the result may be broader than asked"


class QuestionBar:  # pylint: disable=too-many-instance-attributes  # one per element it shows
    """The Question field, the search text's chip and the message line.

    :param service: the model server's service
    :param on_question: asks a Question (the page's)
    :param on_text: runs the search again with an edited search text, or without one (None)
    """

    def __init__(self, service: AiService, on_question: Callable[[str], Awaitable[None]],
                 on_text: Callable[[str | None], Awaitable[None]]):
        self.service = service
        self.busy = False
        self._on_question = on_question
        self._on_text = on_text
        self.text: str | None = None
        with ui.column().classes("w-full gap-1").mark("question-bar"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                self.input = ui.input(label="Question", placeholder=_PLACEHOLDER).classes("flex-grow") \
                    .props("clearable").on("keydown.enter", self._ask).mark("question-input")
                self.chip = ui.chip(icon="manage_search", removable=True, color="secondary", text_color="white",
                                    on_click=self._edit, on_value_change=self._removed).mark("search-chip")
                self.chip.tooltip("The Description search: click to edit")
                self.chip.set_visibility(False)
            self.status = ui.label().classes("text-caption text-grey-7")
            self.progress = ui.linear_progress(show_value=False, size="3px")
            self.message = ui.label().classes("text-caption").mark("question-message")
        self._build_editor()
        self._poll()
        ui.timer(POLL_SECONDS, self._poll)

    def show_text(self, text: str | None) -> None:
        """Shows the search text as the chip, or no chip for None."""
        self.text = text
        self.chip.text = text or ""
        self.chip.value = True
        self.chip.set_visibility(text is not None)

    def show_message(self, text: str, error: bool = False) -> None:
        """Shows a warning (or, with `error`, an error) under the field; an empty text clears it."""
        self.message.text = text
        self.message.classes(replace="text-caption " + ("text-negative" if error else "text-warning"))

    def _poll(self) -> None:
        text = status_text(self.service, self.busy)
        self.status.text = text or ""
        self.status.set_visibility(text is not None)
        self.status.classes(replace="text-caption " + (
            "text-negative" if self.service.state is AiState.FAILED and not self.busy else "text-grey-7"))
        working = self.busy or self.service.state in (AiState.STARTING, AiState.INDEXING)
        self.progress.set_visibility(working)
        self.progress.value = self.service.progress[1]
        enabled = self.service.answers and not self.busy
        self.input.set_enabled(enabled)
        self.chip.set_enabled(enabled)

    async def _ask(self) -> None:
        question = (self.input.value or "").strip()
        if question and self.service.answers and not self.busy:
            await self._on_question(question)

    def _build_editor(self) -> None:
        with ui.dialog() as self._editor, ui.card().classes("w-96"):
            self._editor_input = ui.input(label="Description search").classes("w-full") \
                .on("keydown.enter", self._edited)
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancel", on_click=self._editor.close).props("flat")
                ui.button("Search", icon="manage_search", on_click=self._edited)

    def _edit(self) -> None:
        if self.busy:
            return
        self._editor_input.value = self.text or ""
        self._editor.open()

    async def _edited(self) -> None:
        self._editor.close()
        text = (self._editor_input.value or "").strip() or None
        if text != self.text:
            self.show_text(text)
            await self._on_text(text)

    async def _removed(self) -> None:
        if not self.chip.value and self.text is not None:
            self.show_text(None)
            await self._on_text(None)
