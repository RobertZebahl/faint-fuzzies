"""Converts the Washington Double Star Catalog into the common catalogue format.

Every line of the source is one pair. The pairs of a system share the WDS identifier; a system
with two or more pairs becomes a Group. The group record is written in front of its first pair,
carries the coordinates and constellation of that pair, and is named by the alternative name (a
Bayer or Flamsteed name, when the source gives one) and the WDS id, which always comes last.
Every pair keeps its own names, the WDS id last, and names its group in GROUP.
"""
import re
from dataclasses import dataclass
from typing import Any

from faint_fuzzies.converters.common import Conversion, ConversionProblem, constellation_name, joined_names
from faint_fuzzies.domain.model import ObjectAttribute

_RIGHT_ASCENSION = re.compile(r"(\d{2})(\d{2})(\d{2})(?:\.(\d*))?")
_DECLINATION = re.compile(r"([+-])(\d{2})(\d{2})(\d{2})(?:\.(\d*))?")
_IDENTIFIER_RIGHT_ASCENSION = re.compile(r"(\d{2})(\d{2})(\d)")
_IDENTIFIER_DECLINATION = re.compile(r"([+-])(\d{2})(\d{2})")


@dataclass(frozen=True)
class _Pair:
    """One parsed line of the source file, before it is known whether it joins a group.

    :ivar line: the line number in the source file, 1-based
    :ivar identifier: the WDS identifier shared by every pair of one system, or empty when the line gives none
    :ivar alternative_name: the Bayer or Flamsteed name the line gives, or empty when it gives none
    :ivar component: the pair's component (e.g. "AB"), or empty when the line gives none
    :ivar record: the pair's own record, not yet knowing its GROUP
    """
    line: int
    identifier: str
    alternative_name: str
    component: str
    record: dict[str, Any]


def convert_wds(lines: list[str]) -> Conversion:
    """Converts the lines of the source file into the common catalogue format.

    :param lines: the source file's lines
    :returns: the converted records, or the problems that prevented the conversion
    """
    result = Conversion()
    pairs: list[_Pair] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            pairs.append(_parse_pair(number, line))
        except ValueError as exc:
            result.problems.append(ConversionProblem(number, str(exc)))
    if result.problems:
        return result

    members: dict[str, list[_Pair]] = {}
    for pair in pairs:
        if pair.identifier:
            members.setdefault(pair.identifier, []).append(pair)
    systems = len(members) + sum(1 for p in pairs if not p.identifier)

    group_names = {identifier: _group_name(identifier, systems) for identifier, systems in members.items()
                   if len(systems) > 1}
    written: set[str] = set()
    for pair in pairs:
        group_name = group_names.get(pair.identifier)
        if group_name is None:
            result.records.append(pair.record)
            continue
        if pair.identifier not in written:
            written.add(pair.identifier)
            result.records.append(_group_record(group_name, pair.record))
            _note_duplicate_components(result, group_name, members[pair.identifier])
        result.records.append({**pair.record, ObjectAttribute.GROUP: group_name})
    result.summary = f"converted {len(pairs)} pairs of {systems} systems; {len(group_names)} groups"
    return result


def _group_name(identifier: str, pairs: list[_Pair]) -> str:
    """The name a system's group record is written under: every distinct alternative name its pairs give,
    in the order they first occur, followed by the WDS id, which always comes last.

    :param identifier: the system's WDS identifier
    :param pairs: the system's pairs
    :returns: the formatted name list
    """
    names = list(dict.fromkeys(p.alternative_name for p in pairs if p.alternative_name))
    return joined_names([*names, f"WDS{identifier}"])


def _group_record(name: str, first: dict[str, Any]) -> dict[str, Any]:
    """A group takes coordinates and constellation from its first pair and has no magnitude.

    :param name: the group's name, as built by :func:`_group_name`
    :param first: the system's first pair's record
    :returns: the group's record
    """
    return {ObjectAttribute.GROUP: name, ObjectAttribute.TYPE: "**",
            ObjectAttribute.CONSTELLATION: first[ObjectAttribute.CONSTELLATION],
            ObjectAttribute.COORDINATES: first[ObjectAttribute.COORDINATES]}


def _note_duplicate_components(result: Conversion, group_name: str, pairs: list[_Pair]) -> None:
    """Adds a note to `result` for every component shared by more than one pair of the group, since name
    and component then no longer identify a single pair.

    :param result: the conversion result to add notes to
    :param group_name: the group's name, for the note's text
    :param pairs: the group's pairs
    """
    lines_by_component: dict[str, list[int]] = {}
    for pair in pairs:
        lines_by_component.setdefault(pair.component or "AB", []).append(pair.line)
    for component, lines in lines_by_component.items():
        if len(lines) > 1:
            result.notes.append(f"group {group_name}: component {component} occurs in lines "
                                f"{', '.join(map(str, lines))}, so name and component do not identify one pair")


def _parse_pair(number: int, line: str) -> _Pair:
    """Parses one fixed-width line of the source file into a _Pair, with its record not yet knowing its GROUP.

    :param number: the line's number in the source file, 1-based
    :param line: one line of the source file
    :returns: the parsed pair
    :raises ValueError: when the line is too short, or a field cannot be parsed
    """
    if len(line) < 135:
        raise ValueError(f"line is too short ({len(line)} characters, at least 135 expected)")
    identifier = line[0:10].strip()

    designation = re.sub(r"\s+", " ", line[10:17]).replace(" ", "", 1).strip()
    alternative_name = line[137:].strip() if len(line) > 137 else ""
    names = [designation]
    if alternative_name:
        names.append(alternative_name)
    if identifier:
        names.append(f"WDS{identifier}")

    coordinates = f"{_right_ascension(line[112:121], line[0:5])},{_declination(line[121:130], line[5:10])}"

    magnitudes = [_magnitude(line[58:63]), _magnitude(line[64:69])]
    component = line[17:23].strip()
    if "-" in component:
        raise ValueError(f"component '{component}' contains '-'")
    component = component.replace(",", "-")

    separation = _number(line[52:57], float, "")
    position_angle = _number(line[42:45], int, "")
    year = _number(line[28:32], int, "")
    first_separation = _number(line[46:51], float, "-")
    first_position_angle = _number(line[38:41], int, "-")
    first_year = _number(line[23:27], int, "-")

    record: dict[str, Any] = {
        ObjectAttribute.NAME: joined_names(names),
        ObjectAttribute.TYPE: "**",
        ObjectAttribute.CONSTELLATION: constellation_name(line[132:135]),
        ObjectAttribute.COORDINATES: coordinates,
    }
    if any(magnitudes):
        record[ObjectAttribute.MAGNITUDE] = ";".join(magnitudes)
    record[ObjectAttribute.COMPONENT] = f"{component},{separation},{position_angle},{year}"
    record[ObjectAttribute.DESCRIPTION] = f'Components {first_separation}", {first_position_angle}°, {first_year}'
    return _Pair(number, identifier, alternative_name, component, record)


def _right_ascension(precise: str, identifier: str) -> str:
    """hhmmss.ss from the precise field, else from the identifier, whose last digit counts
    tenths of a minute (six seconds each).

    :param precise: the precise right ascension field
    :param identifier: the WDS identifier, used when `precise` is empty
    :returns: the formatted right ascension
    :raises ValueError: when neither field can be parsed
    """
    text = precise.replace(" ", "")
    match = _RIGHT_ASCENSION.fullmatch(text)
    if match:
        hours, minutes, seconds, fraction = match.groups()
        seconds_value = float(f"{seconds}.{fraction}" if fraction else seconds)
        return f"{int(hours):02d}{int(minutes):02d}{seconds_value:05.2f}"
    match = _IDENTIFIER_RIGHT_ASCENSION.fullmatch(identifier)
    if text in ("", ".") and match:
        hours, minutes, tenths = match.groups()
        return f"{int(hours):02d}{int(minutes):02d}{int(tenths) * 6.0:05.2f}"
    raise ValueError(f"invalid right ascension '{precise.strip()}' (identifier '{identifier}')")


def _declination(precise: str, identifier: str) -> str:
    """±ddmmss.ss from the precise field, else from the identifier (degrees and minutes).

    :param precise: the precise declination field
    :param identifier: the WDS identifier, used when `precise` is empty
    :returns: the formatted declination
    :raises ValueError: when neither field can be parsed
    """
    text = precise.replace(" ", "")
    match = _DECLINATION.fullmatch(text)
    if match:
        sign, degrees, minutes, seconds, fraction = match.groups()
        seconds_value = float(f"{seconds}.{fraction}" if fraction else seconds)
        return f"{sign}{int(degrees):02d}{int(minutes):02d}{seconds_value:05.2f}"
    match = _IDENTIFIER_DECLINATION.fullmatch(identifier)
    if text in ("", ".") and match:
        sign, degrees, minutes = match.groups()
        return f"{sign}{int(degrees):02d}{int(minutes):02d}{0.0:05.2f}"
    raise ValueError(f"invalid declination '{precise.strip()}' (identifier '{identifier}')")


def _magnitude(field_text: str) -> str:
    """A visual-system MAGNITUDE value from one field; empty when the field gives none.

    :param field_text: the raw field
    :returns: the formatted magnitude, or an empty string
    :raises ValueError: when the field is given but not a number
    """
    text = field_text.replace(" ", "")
    if text in ("", "."):
        return ""
    try:
        return f"v{float(text)}"
    except ValueError:
        raise ValueError(f"invalid magnitude '{field_text.strip()}'") from None


def _number(field_text: str, kind: type, missing: Any) -> Any:
    """One field parsed as `kind`, or `missing` when the field is empty or ".".

    :param field_text: the raw field
    :param kind: the type to parse it as, e.g. int or float
    :param missing: the value to return when the field is empty
    :returns: the parsed value, or `missing`
    :raises ValueError: when the field is given but `kind` cannot parse it
    """
    text = field_text.strip(" ")
    if text in ("", "."):
        return missing
    try:
        return kind(text)
    except ValueError:
        raise ValueError(f"invalid number '{text}'") from None
