"""What every importer of community files shares.

Community files are CSV with ";" as separator and, in the published formats, no header line. Each file
is the complete current submission of one observer. Rows with a finding are reported with their
line number and left out; the file itself is never changed.
"""
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.domain.findings import ERROR, CatalogueError, Finding
from faint_fuzzies.domain.model import ObjectType
from faint_fuzzies.domain.observation import Observation, Optic, OpticType, VisibilityEntry
from faint_fuzzies.domain.observer import Observer

RATING_MAP = {"": 0, "*": 1, "**": 2, "***": 3, "0": 0, "1": 1, "2": 2, "3": 3}
_BINOCULARS = re.compile(r"(\d+)x(\d+)")


@dataclass(frozen=True)
class Row:
    """One non-empty row of a community file.

    :ivar line: the line number the row starts on
    :ivar fields: the row's fields, in file order
    """
    line: int
    fields: list[str]


@dataclass
class Candidate:
    """A row that was understood and now needs the Object it describes.

    :ivar line: the line number the row starts on
    :ivar name: the name the row gives
    :ivar component: the component, double stars only; empty when not given
    :ivar object_type: the object type, when it tells same-named objects apart; None otherwise
    :ivar double_star: whether the row is a double star observation
    :ivar observation: the observation the row describes
    """
    line: int
    name: str
    component: str
    object_type: ObjectType | None
    double_star: bool
    observation: Observation


def source_name(path: Path) -> str:
    """How findings and observations name a file: "anna-example/visual.csv", as many observers have a visual.csv.

    :param path: the community file
    :returns: the name findings and observations use for it
    """
    return f"{path.parent.name}/{path.name}"


def read_rows(path: Path) -> list[Row]:
    """The non-empty rows with the line each starts on. UTF-8 is tried first, then Windows-1252.

    :param path: the community file to read
    :returns: the file's non-empty rows
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, or a row is malformed CSV
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CatalogueError(f"cannot read {path}: {exc.strerror}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";", quotechar='"')
    rows = []
    while True:
        start = reader.line_num + 1
        try:
            fields = next(reader)
        except StopIteration:
            return rows
        except csv.Error as exc:
            raise CatalogueError(f"{path.name}: {exc}") from exc
        if any(field.strip() for field in fields):
            rows.append(Row(start, fields))


class RowReport:
    """Collects the findings about one row; the row is left out when any of them is an error.

    :param source: the name of the file the row is in, as :func:`source_name` gives it
    :param line: the line number the row starts on
    :param findings: the list a reported finding is appended to
    """

    def __init__(self, source: str, line: int, findings: list[Finding]):
        self._source, self._line, self._findings = source, line, findings
        self.label: str | None = None
        self.failed = False

    def error(self, attribute: str | None, message: str) -> None:
        """Reports an error on the row, marking it to be left out.

        :param attribute: the attribute the error concerns, or None when it concerns the row as a whole
        :param message: the error message
        """
        self.failed = True
        self._findings.append(Finding(self._source, self._line, self.label, attribute, ERROR, message))


def parse_instrument(text: str) -> Optic | None:
    """"8x40" binoculars, "A" the naked eye, a bare nonzero number a telescope of that aperture.

    :param text: the instrument field's text
    :returns: the parsed optic, or None when the text matches none of the known forms
    """
    text = text.strip()
    match = _BINOCULARS.fullmatch(text)
    if match:
        return Optic(f"B,{text}", OpticType.BINOCULARS, "B", aperture=int(match[2]), magnification=int(match[1]))
    if text in ("A", "a"):
        return Optic("A", OpticType.NAKED_EYE)
    if text != "0" and re.fullmatch(r"\d+", text):
        return Optic(text, OpticType.TELESCOPE, aperture=int(text))
    return None


def build_descriptions(german: str, english: str) -> tuple[str, str]:
    """A description given in one language only is used for both.

    :param german: the German description, possibly empty
    :param english: the English description, possibly empty
    :returns: the (German, English) descriptions, each tidied by :func:`tidied_text`
    """
    if not german and english:
        german = english
    elif not english and german:
        english = german
    return tidied_text(german), tidied_text(english)


def tidied_text(text: str) -> str:
    """Written "\\n" becomes a line break, and more than one empty line becomes one.

    :param text: the raw text
    :returns: the tidied text
    """
    return re.sub(r"\n\n\n+", "\n\n", text.replace("\\n", "\n"))


def file_list(text: str) -> list[str]:
    """A comma-separated field of file names, trimmed of whitespace and empty entries.

    :param text: the comma-separated field
    :returns: the file names, in field order
    """
    return [name.strip() for name in text.split(",") if name.strip()]


def missing_files(names: list[str], directory: Path) -> list[str]:
    """The names, among `names`, of files that do not exist in `directory`.

    :param names: the file names to check
    :param directory: the directory they are expected in
    :returns: the names that have no matching file, in the order given
    """
    return [name for name in names if not (directory / name).is_file()]


def magnification_entry(optic: Optic | None, magnification: str) -> tuple[VisibilityEntry, ...]:
    """The magnification a telescope was used with, kept as an entry without a result.

    :param optic: the optic used, if any
    :param magnification: the magnification field's text
    :returns: a one-element tuple with the magnification entry, or an empty tuple when there is none to keep
    """
    if optic is not None and optic.type is OpticType.TELESCOPE and magnification:
        return (VisibilityEntry(int(magnification), None, None),)
    return ()


def build_community_observation(record: dict, optic: Optic | None, visibility: tuple[VisibilityEntry, ...],
                         observer: Observer, method: str, rating: int, notes: str,
                         source: str) -> Observation:
    """Builds the public Observation of a community-file row.

    :param record: the row's attributes
    :param optic: the optic used, if any
    :param visibility: the row's visibility entries
    :param observer: the observer the row belongs to
    :param method: the observation method
    :param rating: the row's rating
    :param notes: the row's notes
    :param source: the name of the file the row is in, as :func:`source_name` gives it
    :returns: the public Observation
    """
    return Observation(record, public=True, optic=optic, visibility=visibility, observer=observer,
                       method=method, rating=rating, notes=notes, source=source)
