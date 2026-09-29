"""Converts the Herschel catalogue into the common catalogue format.

Fixed columns, the first line is a header. The result is in natural name order. The objects of
the Herschel 400 list are members of the list "400".
"""
import re
from typing import Any

from faint_fuzzies.converters.common import (
    Conversion,
    constellation_name,
    convert_lines,
    coordinates_text,
    joined_names,
    type_codes,
)
from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.domain.model import ObjectType as T

TYPE_MAP = {
    "Galaxy": [T.GALAXY], "Nonexistent": [T.NON_EXISTENT], "Globular clst": [T.GLOBULAR_CLUSTER],
    "Double star": [T.DOUBLE_STAR], "Knot in galax": [T.EXTRAGALACTIC], "Planetary neb": [T.PLANETARY_NEBULA],
    "Nebula": [T.BRIGHT_NEBULA], "Clstr wth neb": [T.OPEN_CLUSTER, T.BRIGHT_NEBULA], "Single star": [T.STAR],
    "Not documnted": [T.GALAXY], "Not documented": [T.GALAXY], "Open cluster": [T.OPEN_CLUSTER],
    "Triple star": [], "Unknown": [], "Asterism": [T.ASTERISM],
}


def convert_herschel(lines: list[str]) -> Conversion:
    """Converts the lines of the source file into the common catalogue format.

    :param lines: the source file's lines, including its header
    :returns: the converted records, or the problems that prevented the conversion
    """
    return convert_lines(lines, 1, _parse_line, (ValueError, KeyError), _message, "objects")


def _message(exc: Exception) -> str:
    """A problem message for an exception raised while parsing one line.

    :param exc: the exception raised by :func:`_parse_line`
    :returns: a human-readable message for it
    """
    return f"unknown value {exc}" if isinstance(exc, KeyError) else str(exc)


def _parse_line(line: str) -> dict[str, Any]:
    """Parses one fixed-width line of the source file into a record.

    :param line: one line of the source file
    :returns: the parsed record
    :raises ValueError: when the line has no object name
    :raises KeyError: when the type text is not in :data:`TYPE_MAP`
    """
    first = re.sub(r"[\s?]", "", line[0:10])
    if not first:
        raise ValueError("no object name given")
    names = [first]
    second = ""
    if len(line) >= 20:
        second = line[10:20]
        if second[-1] != " ":
            second = second[:-1]  # the last column already belongs to the type
        second = second.replace(" ", "")
        if second:
            names.append(second)
    if "H3.182" in names:
        names += ["H3.182.1", "H3.182.2"]

    record: dict[str, Any] = {ObjectAttribute.NAME: joined_names(names)}

    if len(line) >= 33:
        type_text = line[18:33]
        if type_text[0] != " ":
            type_text = type_text[1:]
        type_text = type_text.strip(" ")
        # NGC2459 is marked "not documented", which the source maps to a galaxy; it is an open cluster
        types = [T.OPEN_CLUSTER] if type_text == "Not documnted" and second == "NGC2459" else TYPE_MAP[type_text]
        if types:
            record[ObjectAttribute.TYPE] = type_codes(types)

    if len(line) >= 47 and line[33:46].strip(" ") != "":
        seconds = float(f"{float(line[38:40]) * 60:.2f}") if line[38:40].strip(" ") != "" else 0
        sign = line[41] if line[41] != " " else "+"
        record[ObjectAttribute.COORDINATES] = coordinates_text((int(line[33:35].strip(" ")), int(line[36:38]), seconds),
                                                          (sign, int(line[42:44].strip(" ")), int(line[45:47])))

    if len(line) >= 52:
        size = line[48:52].strip(" ")
        if size not in ("", "NIU"):
            record[ObjectAttribute.SIZE] = f"{float(size)}"

    if len(line) >= 57:
        magnitude = line[53:57].strip(" ")
        if magnitude not in ("", "NIU"):
            if magnitude[-1] == "p":
                magnitude = magnitude[:-1]
            record[ObjectAttribute.MAGNITUDE] = f"v{float(magnitude)}"

    if len(line) >= 61 and line[58:61].strip(" ") != "":
        record[ObjectAttribute.CONSTELLATION] = constellation_name(line[58:61].strip(" "))

    if len(line) >= 64:
        if '"400"' in line[63:]:
            record[ObjectAttribute.GROUP] = "400"
        description = line[63:].strip(" ")
        if description:
            record[ObjectAttribute.DESCRIPTION] = description
    return record
