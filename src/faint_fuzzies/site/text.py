"""Text the pages show. Everything here is a pure function of its arguments. A few formatting oddities
(a falsy zero, a fixed number of decimals) are kept on purpose, documented at each one below."""
import html
import re
import urllib.parse

from faint_fuzzies.domain.formats import normalize_magnitude
from faint_fuzzies.domain.names import name_forms

HTML_MAGNITUDE = '<sup>m</sup><span style="margin-left: -0.55em; margin-right: 0.25em;">.</span>'

_RA = re.compile(r"^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)$")
_DEC = re.compile(r"^([+-])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)$")
_MAGNITUDE = re.compile(r"^[vbp]([+-]?\d+(?:\.\d+)?)$")
_MAGNITUDE_VARIABLE = re.compile(r"^[vbp]([+-]?\d+(?:\.\d+)?)-([+-]?\d+(?:\.\d+)?)$")
_MAGNITUDE_PERIOD = re.compile(r"^P(\d+(?:\.\d+)?)$")
_MAGNITUDE_BV = re.compile(r"^bv([+-]?\d+(?:\.\d+)?)$")


def escape_html(value):
    """html.escape, leaving None as it is.

    :param value: the value to escape
    :returns: the escaped value, or None when `value` is None
    """
    return html.escape(str(value)) if value is not None else value


def quote_url(url: str) -> str:
    """URL-quotes `url`, for an address or a link target. `/` is left alone, the usual path separator.

    :param url: the URL to quote
    :returns: the quoted URL
    """
    return urllib.parse.quote(url)


def quote_anchor(name: str) -> str:
    """URL-quotes `name` for use as an anchor id/name or the fragment linking to it - unlike `quote_url`,
    `/` is quoted too: an anchor is an opaque name, never a path, and a few Object names (a long-period
    comet such as "C/2021 A1 (Leonard)") carry a literal `/` that is not a separator here.

    :param name: the anchor name to quote
    :returns: the quoted anchor name
    """
    return urllib.parse.quote(name, safe="")


def localized_names(value: str, locale: str | None) -> list[str]:
    """The names of a NAME or GROUP value for a language ("de" or "en", None for both): "Lokale Gruppe|Local
    Group" is one name in each language, and every name is followed by its short forms (Messier 13, M13).

    :param value: the record's NAME or GROUP value
    :param locale: "de", "en", or None for both languages
    :returns: the names
    """
    if not value:
        return []
    names = []
    for entry in (part.strip() for part in value.split(",")):
        variants = entry.split("|")
        first = variants[0]
        if len(variants) == 1:
            names.append(first)
        elif locale is None:
            names.extend(variants[:2])
        else:
            names.append(variants[0] if locale == "de" else variants[1])
        names.extend(name_forms(first)[1:])  # short forms come from the first variant, and are for both languages
    return names


def format_coordinates(coordinates: str) -> tuple[str, str] | None:
    """(right ascension, declination) as HTML, or None when the value is missing or not valid.

    :param coordinates: the COORDINATES value
    :returns: (right ascension, declination) as HTML, or None
    """
    parts = (coordinates or "").split(",")
    if len(parts) != 2:
        return None
    ra, dec = _RA.match(parts[0]), _DEC.match(parts[1])
    if not ra or not dec:
        return None
    hours, minutes, seconds = int(ra.group(1)), int(ra.group(2)), float(ra.group(3))
    degrees, arc_minutes, arc_seconds = int(dec.group(2)), int(dec.group(3)), float(dec.group(4))
    return (f"{hours:02d}<sup>h</sup>{minutes:02d}<sup>m</sup>{seconds:05.2f}<sup>s</sup>",
            f"{dec.group(1)}{degrees:02d}°{arc_minutes:02d}'{arc_seconds:05.2f}\"")


def _magnitude_groups(magnitude: str) -> list[dict]:
    """Parses a normalized MAGNITUDE value into its two parts (a double star's primary and secondary,
    semicolon-separated): each part's v/b/p magnitude(s), period (P) and B-V (bv), by their letter.

    :param magnitude: the normalized MAGNITUDE value (see domain.formats.normalize_magnitude)
    :returns: the two parts, each a letter -> its value(s)
    """
    groups: list[dict] = [{}, {}]
    for index, element in enumerate(e.strip() for e in magnitude.split(";")):
        if index > 1:
            break
        for mag in (e.strip() for e in element.split(",")):
            match = _MAGNITUDE.match(mag)
            if match:
                groups[index][mag[0]] = (float(match.group(1)),)
                continue
            match = _MAGNITUDE_VARIABLE.match(mag)
            if match:
                groups[index][mag[0]] = (float(match.group(1)), float(match.group(2)))
                continue
            match = _MAGNITUDE_PERIOD.match(mag)
            if match:
                groups[index]["P"] = float(match.group(1))
                continue
            match = _MAGNITUDE_BV.match(mag)
            if match:
                groups[index]["bv"] = float(match.group(1))
    return groups


def _magnitude_parts(magnitude: str) -> tuple[list[str], list[str | None]]:
    """The brightness of each of the two parts (a double star's primary and secondary) as HTML, and all of them
    in order. The brightness shown is v, else b, else p; a zero counts as missing (a kept oddity, see module
    docstring).

    :param magnitude: the MAGNITUDE value
    :returns: (all brightnesses shown, in order), (primary, secondary), each part None when it has none
    :raises ValueError: when a period is given before any brightness has been shown to attach it to
    """
    shown: list[str] = []
    pair: list[str | None] = [None, None]
    if not magnitude or not magnitude.strip():
        return shown, pair
    for index, group in enumerate(_magnitude_groups(normalize_magnitude(magnitude))):
        kind, values = None, None
        if group.get("v"):
            kind, values = "", group["v"]
        elif group.get("b"):
            kind, values = "b", group["b"]
        elif group.get("p"):
            kind, values = "p", group["p"]
        if kind is not None and values is not None:
            if len(values) == 1:
                text = (f"{kind}{values[0]:.1f}").replace(".", HTML_MAGNITUDE)
            else:
                text = (f"{kind}{values[0]:.1f} - {values[1]:.1f}").replace(".", HTML_MAGNITUDE)
            shown.append(text)
            pair[index] = text
        period = group.get("P")
        if period is not None:
            if not shown:
                raise ValueError("period for a variable star given without magnitudes")
            suffix = f" ({period if period % 1 else int(period)}d)"
            shown[-1] += suffix
            pair[index] = (pair[index] or "") + suffix if pair[index] is not None else None
    return shown, pair


def format_magnitude(magnitude: str) -> str:
    """"v10.3" as HTML with the decimal point after a raised "m"; a second brightness after ";" is joined with
    " / ".

    :param magnitude: the MAGNITUDE value
    :returns: the formatted magnitude
    """
    return " / ".join(_magnitude_parts(magnitude)[0])


def format_magnitude_pair(magnitude: str) -> tuple[str | None, str | None]:
    """The two brightnesses of a double star, each None when missing.

    :param magnitude: the MAGNITUDE value
    :returns: (primary, secondary), each None when missing
    """
    parts = _magnitude_parts(magnitude)[1]
    return parts[0], parts[1]


def format_size(size: str, with_angle: bool = True) -> str:
    """"7.6,3.2,90" as "7.6'&times;3.2' (90°)"; a missing or zero diameter leaves nothing to show.

    :param size: the SIZE value
    :param with_angle: whether the position angle is included when there is one
    :returns: the formatted size, or "" when there is nothing to show
    """
    if not size:
        return ""
    fields = [s.strip() for s in size.split(",")]
    major = float(fields[0]) if fields and fields[0] != "" else None
    minor = float(fields[1]) if len(fields) >= 2 and fields[1] != "" else None
    angle = int(fields[2]) if len(fields) == 3 and fields[2] != "" else None
    if major and minor:
        text = f"{major:.1f}'&times;{minor:.1f}'"
        if with_angle and angle:
            text = f"{text} ({angle}°)"
        return text
    if with_angle and angle:
        return f"({angle}°)"
    return ""
