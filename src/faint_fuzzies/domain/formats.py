"""The formats of the values of an Object's record. Every element of a magnitude is checked, and the flags must be
true or false. Each check gives the message of what is wrong, or None. Nothing here changes a value; the numbers are
not bounded, since the catalogues of others use placeholders (the WDS writes a separation of -1 for "unknown")."""
import re
from collections.abc import Callable
from typing import Any

from faint_fuzzies.domain.model import ObjectAttribute

_MAGNITUDE = (re.compile(r"[vbp][+-]?\d+(?:\.\d+)?"),  # v10.3
              re.compile(r"[vbp][+-]?\d+(?:\.\d+)?-[+-]?\d+(?:\.\d+)?"),  # v9.0-11.5, a variable star
              re.compile(r"P\d+(?:\.\d+)?"),  # P350.5, the period
              re.compile(r"bv[+-]?\d+(?:\.\d+)?"))  # bv0.5, the color index
DSS_SOURCES = ("dss1", "dss2blue", "dss2red")
EQUINOXES = ("J2000.0", "B1950")
FLAGS = (ObjectAttribute.RED_STARS_LIST, ObjectAttribute.DISABLE_DSS, ObjectAttribute.DISABLE_WDS,
        ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS, ObjectAttribute.PUBLISH_WITHOUT_OBSERVATION)
DOUBLE_STAR_LIST_LETTERS = frozenset("BCM")

# The 88 IAU constellation abbreviations, canonically cased ("Aql", "UMa", ...; ten of them, such as UMa
# and CVn, have a second capital, so this cannot be produced by capitalising the first letter alone). A
# source's own casing varies (SAC writes them upper case, "UMA"); this is the single mapping every
# converter normalizes through, rather than each trusting its own source's casing, and what CONSTELLATION
# is checked against below (case-insensitively: casing is not itself an error, a name outside this list is).
# Transcribed from astropy's own constellation_names.dat, which converters.ugc's own computation already uses.
CONSTELLATIONS = {
    "and": "And", "ant": "Ant", "aps": "Aps", "aqr": "Aqr", "aql": "Aql", "ara": "Ara", "ari": "Ari",
    "aur": "Aur", "boo": "Boo", "cae": "Cae", "cam": "Cam", "cnc": "Cnc", "cvn": "CVn", "cma": "CMa",
    "cmi": "CMi", "cap": "Cap", "car": "Car", "cas": "Cas", "cen": "Cen", "cep": "Cep", "cet": "Cet",
    "cha": "Cha", "cir": "Cir", "col": "Col", "com": "Com", "cra": "CrA", "crb": "CrB", "crv": "Crv",
    "crt": "Crt", "cru": "Cru", "cyg": "Cyg", "del": "Del", "dor": "Dor", "dra": "Dra", "equ": "Equ",
    "eri": "Eri", "for": "For", "gem": "Gem", "gru": "Gru", "her": "Her", "hor": "Hor", "hya": "Hya",
    "hyi": "Hyi", "ind": "Ind", "lac": "Lac", "leo": "Leo", "lmi": "LMi", "lep": "Lep", "lib": "Lib",
    "lup": "Lup", "lyn": "Lyn", "lyr": "Lyr", "men": "Men", "mic": "Mic", "mon": "Mon", "mus": "Mus",
    "nor": "Nor", "oct": "Oct", "oph": "Oph", "ori": "Ori", "pav": "Pav", "peg": "Peg", "per": "Per",
    "phe": "Phe", "pic": "Pic", "psc": "Psc", "psa": "PsA", "pup": "Pup", "pyx": "Pyx", "ret": "Ret",
    "sge": "Sge", "sgr": "Sgr", "sco": "Sco", "scl": "Scl", "sct": "Sct", "ser": "Ser", "sex": "Sex",
    "tau": "Tau", "tel": "Tel", "tri": "Tri", "tra": "TrA", "tuc": "Tuc", "uma": "UMa", "umi": "UMi",
    "vel": "Vel", "vir": "Vir", "vol": "Vol", "vul": "Vul",
}


def constellation_name(text: str) -> str:
    """The canonical IAU abbreviation for `text` ("Aql", "UMa", ...), whatever case or spacing the source
    gives it in.

    :param text: the constellation name or abbreviation to canonicalize
    :returns: the canonical IAU abbreviation
    :raises ValueError: when `text` names none of the 88 IAU constellations
    """
    stripped = text.strip()
    canonical = CONSTELLATIONS.get(stripped.casefold())
    if canonical is None:
        raise ValueError(f"unknown constellation '{stripped}'")
    return canonical


def _is_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _is_int(text: str) -> bool:
    try:
        int(text)
    except ValueError:
        return False
    return True


def size_error(value: str) -> str | None:
    """Checks a SIZE value: at most three comma-separated fields (major, minor, angle), the diameters
    numbers and the angle a whole number.

    :param value: the SIZE value to check
    :returns: an error message, or None when the value is valid
    """
    fields = [f.strip() for f in value.split(",")]
    if len(fields) > 3:
        return f"invalid SIZE '{value}': at most three fields (major, minor, angle)"
    if (not all(not f or _is_float(f) for f in fields[:2])
            or (len(fields) == 3 and fields[2] and not _is_int(fields[2]))):
        return f"invalid SIZE '{value}': the diameters are numbers and the angle a whole number"
    return None


def normalize_magnitude(value: str) -> str:
    """A magnitude as `format` writes it: without spaces, and without commas at either end ("v 3.4 ," is
    "v3.4"). The writer, the check and the pages all read a magnitude this way.

    :param value: the magnitude text to normalize
    :returns: the normalized magnitude
    """
    return value.replace(" ", "").strip(" ,")


def magnitude_error(value: str) -> str | None:
    """Checks a MAGNITUDE value: one or two (separated by ';') comma-separated lists of elements, each a
    magnitude ("v10.3"), a variable-star range ("v9.0-11.5"), a period ("P350.5") or a color index ("bv0.5").

    :param value: the MAGNITUDE value to check
    :returns: an error message, or None when the value is valid
    """
    value = normalize_magnitude(value)
    parts = [p.strip() for p in value.split(";")]
    if len(parts) > 2:
        return f"invalid MAGNITUDE '{value}': at most two parts, separated by ';'"
    for part in parts:
        for element in (e.strip() for e in part.split(",")):
            if element and not any(pattern.fullmatch(element) for pattern in _MAGNITUDE):
                return (f"invalid MAGNITUDE '{value}': '{element}' is none of "
                        "v10.3, b10.3, p10.3, v9.0-11.5, P350.5, bv0.5")
    return None


def has_second_magnitude(value: str) -> bool:
    """Whether a MAGNITUDE value gives a second magnitude (after the ';') - a double star's secondary.

    :param value: the MAGNITUDE value to check
    :returns: whether it has a second part
    """
    parts = normalize_magnitude(value).split(";")
    return len(parts) > 1 and bool(parts[1].strip())


def component_error(value: str) -> str | None:
    """Checks a COMPONENT value: at most four comma-separated fields (name, separation, angle, year), the
    separation a number and the angle and year whole numbers.

    :param value: the COMPONENT value to check
    :returns: an error message, or None when the value is valid
    """
    fields = [f.strip() for f in value.split(",")]
    if len(fields) > 4:
        return f"invalid COMPONENT '{value}': at most four fields (name, separation, angle, year)"
    if len(fields) > 1 and fields[1] and not _is_float(fields[1]):
        return f"invalid COMPONENT '{value}': the separation is a number"
    if any(f and not _is_int(f) for f in fields[2:]):
        return f"invalid COMPONENT '{value}': the angle and the year are whole numbers"
    return None


def dss_error(value: str) -> str | None:
    """Checks a DSS value: at most two comma-separated fields (survey, field of view), the survey one of
    DSS_SOURCES and the field of view a number.

    :param value: the DSS value to check
    :returns: an error message, or None when the value is valid
    """
    fields = [f.strip() for f in value.split(",")]
    if len(fields) > 2:
        return f"invalid DSS '{value}': at most two fields (survey, field of view)"
    if fields[0] and fields[0].casefold() not in DSS_SOURCES:
        return f"invalid DSS '{value}': the survey is one of {', '.join(DSS_SOURCES)}"
    if len(fields) == 2 and fields[1] and not _is_float(fields[1]):
        return f"invalid DSS '{value}': the field of view is a number"
    return None


def equinox_error(value: str) -> str | None:
    """Checks an EQUINOX value against EQUINOXES.

    :param value: the EQUINOX value to check
    :returns: an error message, or None when the value is valid
    """
    return None if value in EQUINOXES else f"invalid EQUINOX '{value}': one of {', '.join(EQUINOXES)}"


def constellation_error(value: str) -> str | None:
    """None of the 88 IAU constellations, case-insensitively - a typo, distinct from constellation_findings'
    check that a valid CONSTELLATION matches the one computed from COORDINATES (see checks.py).

    :param value: the CONSTELLATION value to check
    :returns: an error message, or None when the value is valid
    """
    if value.strip().casefold() in CONSTELLATIONS:
        return None
    return f"invalid CONSTELLATION '{value}': none of the 88 IAU constellations"


def double_star_lists_error(value: str) -> str | None:
    """Checks a PROJECT_DOUBLE_STARS_LISTS value: only the letters B, C and M.

    :param value: the PROJECT_DOUBLE_STARS_LISTS value to check
    :returns: an error message, or None when the value is valid
    """
    if set(value) <= DOUBLE_STAR_LIST_LETTERS:
        return None
    return f"invalid PROJECT_DOUBLE_STARS_LISTS '{value}': the letters B, C and M only"


# attribute -> the check of its text; a value that is not text is an error of its own, an empty one is none
TEXT_CHECKS: dict[str, Callable[[str], str | None]] = {
    ObjectAttribute.SIZE: size_error, ObjectAttribute.MAGNITUDE: magnitude_error,
    ObjectAttribute.COMPONENT: component_error, ObjectAttribute.DSS: dss_error,
    ObjectAttribute.EQUINOX: equinox_error,
    ObjectAttribute.PROJECT_DOUBLE_STARS_LISTS: double_star_lists_error,
    ObjectAttribute.CONSTELLATION: constellation_error,
}
RATINGS = (ObjectAttribute.RATING, ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING)


def value_errors(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Checks every value of a record against its format.

    :param record: the record to check
    :returns: (attribute, message) for every value that is not in its format
    """
    errors: list[tuple[str, str]] = []
    for attribute, check in TEXT_CHECKS.items():
        value = record.get(attribute)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            errors.append((attribute, f"{attribute} must be a string"))
        elif (message := check(value)) is not None:
            errors.append((attribute, message))
    for attribute in RATINGS:
        value = record.get(attribute)
        if value is not None and not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3):
            errors.append((attribute, f"invalid {attribute} {value!r}: a whole number from 0 to 3"))
    for attribute in FLAGS:
        value = record.get(attribute)
        if value is not None and not isinstance(value, bool):
            errors.append((attribute, f"invalid {attribute} {value!r}: true or false"))
    return errors
