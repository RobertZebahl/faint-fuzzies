"""Converts the Uppsala General Catalogue into the common catalogue format.

The VizieR "VII/26D" export: a five-line header (a comment, a dashed rule, two header rows and
another dashed rule), then one "|"-delimited line per object, and a final dashed rule. The
positions are given for the equinox B1950, and the constellation is computed from them. Every
object also carries an MCG designation, added as a second name.
"""
from typing import Any

from faint_fuzzies.converters.common import (
    Conversion,
    ConversionProblem,
    constellation_name,
    coordinates_text,
    joined_names,
    size_text,
)
from faint_fuzzies.domain.model import ObjectAttribute, ObjectType

HEADER_LINES = 5


def convert_ugc(lines: list[str]) -> Conversion:
    """Converts the lines of the source file into the common catalogue format.

    :param lines: the source file's lines, including its header
    :returns: the converted records, or the problems that prevented the conversion
    """
    result = Conversion()
    records = []
    for number, line in enumerate(lines[HEADER_LINES:], start=HEADER_LINES + 1):
        if not line.strip() or _is_rule(line):
            continue
        try:
            records.append(_parse_line(line))
        except (ValueError, IndexError) as exc:
            result.problems.append(
                ConversionProblem(number, "line is too short" if isinstance(exc, IndexError) else str(exc))
            )
    if result.problems:
        return result
    for record, constellation in zip(records, _constellations([r[ObjectAttribute.COORDINATES] for r in records])):
        record[ObjectAttribute.CONSTELLATION] = constellation
    result.records = [_ordered(r) for r in records]
    result.summary = f"converted {len(records)} objects"
    return result


def _is_rule(line: str) -> bool:
    """Whether `line` is one of the file's dashed rules (the header's closing one, or the trailing one
    after the last object), which carries no data and is not a broken line either.

    :param line: the line to check
    :returns: whether it is a dashed rule
    """
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= {"-"}


def _ordered(record: dict[str, Any]) -> dict[str, Any]:
    """`record` with its keys in the catalogue's canonical attribute order, for a stable file layout.

    :param record: the record to reorder
    :returns: the same record, with its keys reordered
    """
    order = (ObjectAttribute.NAME, ObjectAttribute.TYPE, ObjectAttribute.CONSTELLATION, ObjectAttribute.COORDINATES,
            ObjectAttribute.EQUINOX, ObjectAttribute.MAGNITUDE, ObjectAttribute.SIZE)
    return {key: record[key] for key in order if key in record}


def _parse_line(line: str) -> dict[str, Any]:
    """Parses one "|"-delimited line of the source file into a record. The CONSTELLATION attribute is
    filled in separately, by :func:`_constellations`, once every record of the file is parsed.

    :param line: one line of the source file
    :returns: the parsed record
    :raises ValueError: when a field cannot be parsed
    :raises IndexError: when the line has too few fields
    """
    # UGC|A|RA Dec|MCG|POSS|major|minor|PA|Hubble|Pmag|RadVel|major(red)|minor(red)|i - POSS, Hubble,
    # RadVel and i are not used by the common format, see the module docstring for all of them
    fields = line.split("|")
    if len(fields) < 14:
        raise IndexError
    name = f"UGC{fields[0].replace('UGC', '').strip()}{fields[1].strip()}"
    mcg = fields[3].strip()
    record: dict[str, Any] = {
        ObjectAttribute.NAME: joined_names([name, mcg]) if mcg else name,
        ObjectAttribute.TYPE: ObjectType.GALAXY.value,
        ObjectAttribute.COORDINATES: _coordinates(fields[2]),
        ObjectAttribute.EQUINOX: "B1950",
    }
    magnitude = fields[9].strip()
    if magnitude:
        record[ObjectAttribute.MAGNITUDE] = f"b{float(magnitude)}"

    size = size_text(_larger(fields[5], fields[11]), _larger(fields[6], fields[12]),
                     int(fields[7].strip()) if fields[7].strip() else "")
    if size:
        record[ObjectAttribute.SIZE] = size
    return record


def _coordinates(position: str) -> str:
    """The COORDINATES a position field gives ("RAh RAm +Dd Dm", declination minutes always whole).

    :param position: the position field, as :func:`_parse_line` splits it off
    :returns: the formatted coordinates
    :raises ValueError: when the field cannot be parsed
    """
    tokens = position.split()
    if len(tokens) != 4:
        raise ValueError(f"invalid position '{position.strip()}'")
    right_ascension_hours, right_ascension_minutes, declination_sign_degrees, declination_minutes = tokens
    minutes = float(right_ascension_minutes)
    seconds = round((minutes - int(minutes)) * 60, 2)
    return coordinates_text((int(right_ascension_hours), int(minutes), seconds),
                            (declination_sign_degrees[0], int(declination_sign_degrees[1:]), int(declination_minutes)))


def _larger(first: str, second: str) -> float | str:
    """The source gives two measurements; the larger one is kept.

    Compared as numbers, not as text - comparing as text would make "8." beat "10.".

    :param first: the first measurement's text, or empty when not given
    :param second: the second measurement's text, or empty when not given
    :returns: the larger of the two, or empty when neither is given
    """
    first, second = first.strip(), second.strip()
    if not first:
        return float(second) if second else ""
    return max(float(first), float(second)) if second else float(first)


def _constellations(coordinate_texts: list[str]) -> list[str]:
    """The IAU constellation of each position, for the equinox B1950 as the source states it.

    :param coordinate_texts: the formatted COORDINATES of each record, as :func:`_parse_line` built them
    :returns: the constellation name of each position, in the same order
    """
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    right_ascensions, declinations = [], []
    for text in coordinate_texts:
        ra, dec = text.split(",")
        right_ascensions.append(int(ra[0:2]) + int(ra[2:4]) / 60.0 + float(ra[4:]) / 3600.0)
        degrees = int(dec[1:3]) + int(dec[3:5]) / 60.0 + float(dec[5:]) / 3600.0
        declinations.append(-degrees if dec[0] == "-" else degrees)
    positions = SkyCoord(right_ascensions * u.hour, declinations * u.deg, frame="fk4", equinox="B1950")
    # astropy already returns the canonical IAU casing (it comes from the same table constellation_name
    # does), so this is a no-op today; routed through it anyway so every converter agrees through one
    # mapping rather than each trusting its own source of the casing.
    return [constellation_name(str(name)) for name in positions.get_constellation(short_name=True)]
