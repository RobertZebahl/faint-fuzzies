"""What every converter of a source catalogue shares."""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from faint_fuzzies.domain.formats import constellation_name  # noqa: F401  # pylint: disable=unused-import
from faint_fuzzies.domain.model import ObjectAttribute, ObjectType
from faint_fuzzies.domain.sorting import natural_sort_key

TYPE_ORDER = {t: position for position, t in enumerate(ObjectType)}


@dataclass(frozen=True)
class ConversionProblem:
    """One line of the source file that could not be converted.

    :ivar line: the line number in the source file, 1-based
    :ivar message: why the line could not be converted
    """
    line: int
    message: str


@dataclass
class Conversion:
    """The records of a converted catalogue, or the problems that prevented the conversion.

    :ivar records: the converted records, empty when `problems` is not
    :ivar problems: the lines that could not be converted; non-empty means the conversion failed
    :ivar notes: remarks about the conversion that are not problems (e.g. a source quirk that was worked
        around), shown to the user alongside the result
    :ivar summary: a one-line summary of the result, e.g. "converted 123 objects"
    """
    records: list[dict[str, Any]] = field(default_factory=list)
    problems: list[ConversionProblem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    summary: str = ""


def convert_lines(lines: list[str], header_lines: int, parse_line: Callable[[str], dict[str, Any]],
                  exceptions: tuple[type[Exception], ...], message: Callable[[Exception], str],
                  noun: str) -> Conversion:
    """Converts every non-blank line after the header, one at a time, into the common catalogue format: the
    lines a converter shares with every other converter whose records are independent of each other
    (a source with cross-line structure, such as a WDS pair joining a group, parses its lines itself instead).

    :param lines: the lines of the source file, including its header
    :param header_lines: how many lines at the start are the header, not data
    :param parse_line: the record of one data line, or the error it raises when the line cannot be used
    :param exceptions: the exception types `parse_line` can raise for a line that cannot be used
    :param message: a problem message for an exception `parse_line` raised
    :param noun: what was converted, for the summary ("converted N `noun`")
    :returns: the converted records, sorted by name, or the problems that prevented the conversion
    """
    result = Conversion()
    records = []
    for number, line in enumerate(lines[header_lines:], start=header_lines + 1):
        if not line.strip():
            continue
        try:
            records.append(parse_line(line))
        except exceptions as exc:
            result.problems.append(ConversionProblem(number, message(exc)))
    if result.problems:
        return result
    result.records = sort_by_name(records)
    result.summary = f"converted {len(records)} {noun}"
    return result


def joined_names(names: list[str]) -> str:
    """A comma separated name list, written as the catalogue format has it: "a, b".

    :param names: the names to join
    :returns: the joined, comma-separated list
    """
    return ", ".join(part.strip() for part in ", ".join(names).split(","))


def type_codes(types: list[ObjectType]) -> str:
    """The type codes in their canonical order; an empty list gives an empty string.

    :param types: the object types to encode
    :returns: the comma-separated type codes
    """
    return ",".join(t.value for t in sorted(types, key=TYPE_ORDER.__getitem__))


def sort_by_name(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Natural order of the comma-joined names; records with equal names keep their order.

    :param records: the records to sort, each with a NAME attribute
    :returns: the records, sorted
    """
    return sorted(records, key=lambda r: natural_sort_key(
        ",".join(n.strip() for n in r[ObjectAttribute.NAME].split(","))))


def coordinates_text(right_ascension: tuple[int, int, float], declination: tuple[str, int, int]) -> str:
    """"hhmmss.ss,±ddmmss" with the declination seconds always zero, as these catalogues give them.

    :param right_ascension: (hours, minutes, seconds)
    :param declination: (sign, degrees, arcminutes)
    :returns: the formatted coordinates
    """
    hours, minutes, seconds = right_ascension
    sign, degrees, arcminutes = declination
    return f"{hours:02d}{minutes:02d}{seconds:05.2f},{sign}{degrees:02d}{arcminutes:02d}{0:02d}"


def size_text(largest: Any, smallest: Any, position_angle: Any) -> str | None:
    """"max,min,pa" when any part is given (a zero counts as not given); a missing part is empty.

    :param largest: the largest axis
    :param smallest: the smallest axis
    :param position_angle: the position angle
    :returns: the formatted size, or None when none of the three parts is given
    """
    if largest or smallest or position_angle:
        return f"{largest},{smallest},{position_angle}"
    return None
