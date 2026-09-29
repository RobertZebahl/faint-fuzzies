"""Text the pages show. Everything here is a pure function of its arguments.

Magnitude and size formatting used to live here too, as format_magnitude/format_magnitude_pair/
magnitude_pair_values/format_size; both are now hand-ported to PHP instead (site/static/php/magnitude.php,
size.php, shipped with the data directory), since every caller needed the raw value in the template anyway
(to compare it against a threshold, or because several templates rendered the same value independently).
format_coordinates stays here: besides HTML, it is also used as a plain validity check."""
import html
import re
import urllib.parse

from faint_fuzzies.domain.names import name_forms

HTML_MAGNITUDE = '<sup>m</sup><span style="margin-left: -0.55em; margin-right: 0.25em;">.</span>'

_RA = re.compile(r"^(\d{2})(\d{2})(\d{2}(?:\.\d+)?)$")
_DEC = re.compile(r"^([+-])(\d{2})(\d{2})(\d{2}(?:\.\d+)?)$")


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
