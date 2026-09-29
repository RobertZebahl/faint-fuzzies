"""Converts the Saguaro Astronomy Club database into the common catalogue format.

One object per line, fields separated by "|", the first line is a header. The result is in
natural name order.
"""
from typing import Any

from faint_fuzzies.converters.common import (
    Conversion,
    constellation_name,
    convert_lines,
    coordinates_text,
    joined_names,
    size_text,
    type_codes,
)
from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.domain.model import ObjectType as T

TYPE_MAP = {
    "GALXY": [T.GALAXY], "2STAR": [T.DOUBLE_STAR], "1STAR": [T.STAR],
    "G+C+N": [T.EXTRAGALACTIC, T.OPEN_CLUSTER, T.BRIGHT_NEBULA], "OPNCL": [T.OPEN_CLUSTER],
    "PLNNB": [T.PLANETARY_NEBULA], "GALCL": [T.GALAXY_CLUSTER], "3STAR": [], "4STAR": [], "8STAR": [],
    "GLOCL": [T.GLOBULAR_CLUSTER], "ASTER": [T.ASTERISM], "DRKNB": [T.DARK_NEBULA],
    "BRTNB": [T.BRIGHT_NEBULA], "NONEX": [T.NON_EXISTENT], "SNREM": [T.BRIGHT_NEBULA, T.EMISSION_NEBULA],
    "CL+NB": [T.OPEN_CLUSTER, T.BRIGHT_NEBULA], "QUASR": [T.QUASAR],
    "GX+DN": [T.EXTRAGALACTIC, T.BRIGHT_NEBULA], "LMCOC": [T.EXTRAGALACTIC, T.OPEN_CLUSTER],
    "LMCGC": [T.EXTRAGALACTIC, T.GLOBULAR_CLUSTER], "LMCDN": [T.EXTRAGALACTIC, T.OPEN_CLUSTER],
    "LMCCN": [T.EXTRAGALACTIC, T.OPEN_CLUSTER, T.BRIGHT_NEBULA], "GX+GC": [T.EXTRAGALACTIC, T.GLOBULAR_CLUSTER],
    "SMCCN": [T.EXTRAGALACTIC, T.OPEN_CLUSTER, T.BRIGHT_NEBULA], "SMCGC": [T.EXTRAGALACTIC, T.GLOBULAR_CLUSTER],
    "SMCOC": [T.EXTRAGALACTIC, T.OPEN_CLUSTER], "SMCDN": [T.EXTRAGALACTIC, T.BRIGHT_NEBULA],
}
MAGNITUDE_LIMIT = 32  # from this magnitude on the source means "unknown"


def convert_sac(lines: list[str]) -> Conversion:
    """Converts the lines of the source file into the common catalogue format.

    :param lines: the source file's lines, including its header
    :returns: the converted records, or the problems that prevented the conversion
    """
    return convert_lines(lines, 1, _parse_line, (ValueError, KeyError, IndexError), _message, "objects")


def _message(exc: Exception) -> str:
    """A problem message for an exception raised while parsing one line.

    :param exc: the exception raised by :func:`_parse_line`
    :returns: a human-readable message for it
    """
    if isinstance(exc, KeyError):
        return f"unknown value {exc}"
    if isinstance(exc, IndexError):
        return "line has too few fields"
    return str(exc)


def _parse_line(line: str) -> dict[str, Any]:
    """Parses one "|"-separated line of the source file into a record.

    :param line: one line of the source file
    :returns: the parsed record
    :raises ValueError: when a field cannot be parsed, or the line has no object name
    :raises KeyError: when the type code is unknown
    :raises IndexError: when the line has too few fields
    """
    fields = line.strip("|").split("|")
    first = fields[0].replace(" ", "")
    if not first:
        raise ValueError("no object name given")
    names = [first] + [n for n in (e.replace(" ", "") for e in fields[1].split(";")) if n]

    right_ascension = fields[4]
    declination = fields[5]
    coordinate_text = coordinates_text(
        (int(right_ascension[0:2]), int(right_ascension[3:5]),
         float(f"{float(right_ascension[5:7]) * 60:.2f}")),
        (declination[0], int(declination[1:3]), int(declination[4:6])))

    record: dict[str, Any] = {ObjectAttribute.NAME: joined_names(names)}
    types = type_codes(TYPE_MAP[fields[2]])
    if types:
        record[ObjectAttribute.TYPE] = types
    if fields[3]:
        record[ObjectAttribute.CONSTELLATION] = constellation_name(fields[3])
    record[ObjectAttribute.COORDINATES] = coordinate_text

    magnitude = fields[6].strip(" ")
    if magnitude and float(magnitude) < MAGNITUDE_LIMIT:
        record[ObjectAttribute.MAGNITUDE] = f"v{float(magnitude)}"

    position_angle = fields[12].replace(" ", "")
    size = size_text(_size(fields[10]), _size(fields[11]), int(position_angle) if position_angle else "")
    if size:
        record[ObjectAttribute.SIZE] = size

    description = []
    if fields[13].strip(" "):
        description.append(f"Class: {fields[13].strip(' ')}")
    if fields[17].strip(" "):
        description.append(f"NGC description: {fields[17].strip(' ')}")
    if fields[18].strip(" "):
        description.append(f"Notes: {fields[18].strip(' ')}")
    if description:
        record[ObjectAttribute.DESCRIPTION] = "; ".join(description)
    return record


def _size(text: str) -> float | str:
    """A size in arcminutes ("1.5 m") or arcseconds ("30 s"); empty when not given.

    :param text: the field's raw text
    :returns: the size in arcminutes, or an empty string when not given
    :raises ValueError: when the text has no recognized unit
    """
    size = text.replace(" ", "")
    if not size:
        return ""
    if size[-1] not in "ms":
        raise ValueError("no unit for size")
    value = float(size[:-1])
    if size[-1] == "s":
        value /= 60.0
    return float(f"{value:.2f}")
