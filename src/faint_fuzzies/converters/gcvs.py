"""Converts the General Catalogue of Variable Stars into the common catalogue format.

Fields separated by "|". A data line's first field (NNo) is always the two-digit constellation
number followed by four more digits and then either a further digit, a component letter (as in
"180106A"/"180106B") or a space - seven characters in all, immediately followed by "|" - so a line
that does not look like that (a header, a column-rule line of dashes, or any number of either) is
skipped instead of parsed; the source is not known to always have the same number of them, and has
in fact been seen both with two header lines and with none at all. Every star is a variable star;
the magnitude is the range of the brightness, and the period follows when known. The result is in
natural name order.
"""
import re
from typing import Any

from faint_fuzzies.converters.common import Conversion, ConversionProblem, sort_by_name, type_codes
from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.domain.model import ObjectType as T

_DATA_LINE = re.compile(r"^\d{6}[0-9A-Za-z ]\|")
CONSTELLATIONS = {
    "01": "And", "02": "Ant", "03": "Aps", "04": "Aqr", "05": "Aql", "06": "Ara", "07": "Ari", "08": "Aur",
    "09": "Boo", "10": "Cae", "11": "Cam", "12": "Cnc", "13": "CVn", "14": "CMa", "15": "CMi", "16": "Cap",
    "17": "Car", "18": "Cas", "19": "Cen", "20": "Cep", "21": "Cet", "22": "Cha", "23": "Cir", "24": "Col",
    "25": "Com", "26": "CrA", "27": "CrB", "28": "Crv", "29": "Crt", "30": "Cru", "31": "Cyg", "32": "Del",
    "33": "Dor", "34": "Dra", "35": "Equ", "36": "Eri", "37": "For", "38": "Gem", "39": "Gru", "40": "Her",
    "41": "Hor", "42": "Hya", "43": "Hyi", "44": "Ind", "45": "Lac", "46": "Leo", "47": "LMi", "48": "Lep",
    "49": "Lib", "50": "Lup", "51": "Lyn", "52": "Lyr", "53": "Men", "54": "Mic", "55": "Mon", "56": "Mus",
    "57": "Nor", "58": "Oct", "59": "Oph", "60": "Ori", "61": "Pav", "62": "Peg", "63": "Per", "64": "Phe",
    "65": "Pic", "66": "Psc", "67": "PsA", "68": "Pup", "69": "Pyx", "70": "Ret", "71": "Sge", "72": "Sgr",
    "73": "Sco", "74": "Scl", "75": "Sct", "76": "Ser", "77": "Sex", "78": "Tau", "79": "Tel", "80": "Tri",
    "81": "TrA", "82": "Tuc", "83": "UMa", "84": "UMi", "85": "Vel", "86": "Vir", "87": "Vol", "88": "Vul",
}
_RIGHT_ASCENSION = re.compile(r"^(\d{2})(\d{2})(\d{2}(\.\d+)?)$")
_DECLINATION = re.compile(r"^([+-])(\d{2})(\d{2})(\d{2}(\.\d+)?)$")
_MAGNITUDE = re.compile(r"^[vbp]([+-]?\d+(?:\.\d+)?)$")
_MAGNITUDE_RANGE = re.compile(r"^[vbp]([+-]?\d+(?:\.\d+)?)-([+-]?\d+(?:\.\d+)?)$")
_MAGNITUDE_BV = re.compile(r"^bv([+-]?\d+(?:\.\d+)?)$")
_PERIOD = re.compile(r"^P(\d+(?:\.\d+)?)$")


def convert_gcvs(lines: list[str]) -> Conversion:
    """Converts the lines of the source file into the common catalogue format.

    :param lines: the source file's lines, including its header, if it has one (see :data:`_DATA_LINE`)
    :returns: the converted records, or the problems that prevented the conversion
    """
    result = Conversion()
    records = []
    for number, line in enumerate(lines, start=1):
        if not _DATA_LINE.match(line):
            continue
        try:
            records.append(_parse_line(line))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            result.problems.append(ConversionProblem(number, _message(exc)))
    if result.problems:
        return result
    result.records = sort_by_name(records)
    result.summary = f"converted {len(records)} stars"
    return result


def _message(exc: Exception) -> str:
    """A problem message for an exception raised while parsing one line.

    :param exc: the exception raised by :func:`_parse_line`
    :returns: a human-readable message for it
    """
    if isinstance(exc, KeyError):
        return f"unknown constellation number {exc}"
    if isinstance(exc, IndexError):
        return "line has too few fields"
    return str(exc)


def _parse_line(line: str) -> dict[str, Any]:
    """Parses one "|"-separated line of the source file into a record.

    :param line: one line of the source file
    :returns: the parsed record
    :raises ValueError: when a field cannot be parsed
    :raises KeyError: when the constellation number is unknown
    :raises IndexError: when the line has too few fields
    """
    fields = line.split("|")
    name = re.sub(r"\*$", "", re.sub(r"\s+", " ", fields[1])).strip()
    record: dict[str, Any] = {
        ObjectAttribute.NAME: name,
        ObjectAttribute.TYPE: type_codes([T.STAR, T.VARIABLE_STAR]),
        ObjectAttribute.CONSTELLATION: CONSTELLATIONS[fields[0][0:2]],
    }

    tokens = re.sub(r"\s+", " ", fields[2].replace(":", "")).strip().split(" ")
    if len(tokens) == 2:
        right_ascension, declination = tokens[0].strip("."), tokens[1].strip(".")
        if _RIGHT_ASCENSION.match(right_ascension) and _DECLINATION.match(declination):
            record[ObjectAttribute.COORDINATES] = f"{right_ascension},{declination}"

    magnitude = _magnitude(fields)
    if magnitude:
        record[ObjectAttribute.MAGNITUDE] = magnitude
    return record


def _clean(text: str, remove: str) -> str:
    for character in remove:
        text = text.replace(character, "")
    return text.strip()


def _sum(brightest: float, difference: float) -> float:
    """The faintest magnitude from the brightest one and the difference. The source has two decimals;
    rounding avoids floating-point sums such as 11.899999999999999.

    :param brightest: the brightest magnitude
    :param difference: the difference to the faintest magnitude
    :returns: the faintest magnitude, rounded to two decimals
    """
    return round(brightest + difference, 2)


def _magnitude(fields: list[str]) -> str:
    """The MAGNITUDE attribute from a line's fields: a range (and, when known, a period), in the system
    (visual, blue or photographic) the line gives; empty when the fields give nothing usable.

    :param fields: the line's "|"-separated fields
    :returns: the formatted magnitude, or an empty string
    """
    brightest_text = _clean(fields[4], ":<>")
    brightest = float(brightest_text) if brightest_text else None

    faintest_text = _clean(fields[5], ":*<>")
    faintest: float | None
    if re.match(r"^\d+\.\d*$", faintest_text):
        faintest = float(faintest_text)
    else:
        as_difference = re.match(r"^\(\s*(\d+\.\d*)\s*\)$", faintest_text)
        faintest = _sum(brightest, float(as_difference.group(1))) if as_difference and brightest is not None else None

    system = {"V": "v", "B": "b", "p": "p"}.get(fields[7].strip())

    period_text = _clean(fields[10], ":()")
    period = float(period_text) if re.match(r"^\d+\.\d*$", period_text) else None

    parts = []
    if brightest is not None and faintest is not None and system is not None:
        parts.append(f"{system}{brightest}-{faintest}")
        if period is not None:
            parts.append(f"P{period}")
    text = ",".join(parts)
    return text if _is_valid(text) else ""


def _is_valid(text: str) -> bool:
    """Whether a formatted magnitude is well-formed. Only the last entry of a list is examined; the
    others are assumed valid.

    :param text: the formatted magnitude, as built by :func:`_magnitude`
    :returns: whether it is well-formed
    """
    for element in (e.strip() for e in text.split(";")):
        valid = True
        for entry in (m.strip() for m in element.split(",")):
            if entry:
                valid = bool(_MAGNITUDE.match(entry) or _MAGNITUDE_BV.match(entry)
                             or _PERIOD.match(entry) or _MAGNITUDE_RANGE.match(entry))
        if not valid:
            return False
    return True
