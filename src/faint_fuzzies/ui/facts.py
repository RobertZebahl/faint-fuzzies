"""What the detail panel says about an Object itself, as labeled values: where it is, what it is, how bright and how
large, its rating and marks, and what else its record holds. Only what the record (or, for a double star, the entry of
another catalogue it references) actually says is given, in words and units rather than as written. Nothing here
touches the user interface, so it can be tested without one."""
from dataclasses import dataclass
from typing import Any

from faint_fuzzies.domain.formats import normalize_magnitude
from faint_fuzzies.domain.model import (
    COORDINATES_FORMAT,
    OBJECT_ATTRIBUTES,
    Object,
    ObjectAttribute,
    ObjectType,
    split_names,
)
from faint_fuzzies.domain.references import References, wds_reference
from faint_fuzzies.domain.seen import SeenStatus

# the letters of PROJECT_DOUBLE_STARS_LISTS
DOUBLE_STAR_LISTS = {"B": "binoculars", "C": "colored", "M": "multiple systems"}
SEEN_TEXT = {SeenStatus.SEEN: "seen", SeenStatus.FAILED: "failed", SeenStatus.NOT_OBSERVED: "not observed"}
# what the record can say that the panel (or the Observations below it) shows on its own; an attribute the tool does
# not know is listed as it is
_KNOWN = frozenset(OBJECT_ATTRIBUTES)


@dataclass(frozen=True)
class Fact:
    """One labeled value of the detail panel.

    :ivar label: the fact's label
    :ivar value: the fact's value, already formatted in words and units
    :ivar source: the catalogue a value was taken from when the Object has none of its own; empty otherwise
    """
    label: str
    value: str
    source: str = ""


def object_facts(obj: Object, references: References | None = None, seen: SeenStatus | None = None) -> list[Fact]:
    """The facts about the Object, in the order the panel shows them.

    :param obj: the Object to describe
    :param references: lets a double star take what its own record lacks (usually the position, the
        magnitude and the separation) from the WDS pair it references - never any other catalogue's;
        without them only the record speaks (an Invalid Object has none)
    :param seen: the Object's Seen status, shown as a fact when given
    :returns: the facts, in panel order
    """
    record = obj.record
    facts: list[Fact] = [Fact("Record", f"{obj.catalogue}, number {obj.number}")]

    def add(label: str, _value: Any, _source: str = "") -> None:
        text = str(_value).strip() if _value is not None else ""
        if text:
            facts.append(Fact(label, text, _source))

    def resolved(_key: str) -> tuple[str, str]:
        """The Object's own value of an attribute, else its WDS reference's (never any other catalogue's,
        see references.wds_reference), and the catalogue that gave it."""
        value = record.get(_key)
        if value:
            return str(value), ""
        wds = wds_reference(obj, references)
        if wds is not None and wds.record.get(_key):
            return str(wds.record[_key]), wds.catalogue
        return "", ""

    if obj.types:
        add("Type", ", ".join(f"{t.value} ({_type_name(t)})" for t in obj.types))
    if obj.groups and obj.names:
        add("Group", ", ".join(split_names(str(record.get(ObjectAttribute.GROUP, ""))) or obj.groups))
    add("Constellation", obj.constellation)

    value, source = resolved(ObjectAttribute.COORDINATES)
    add("Coordinates", _coordinates(value), source)
    add("Equinox", record.get(ObjectAttribute.EQUINOX))

    value, source = resolved(ObjectAttribute.MAGNITUDE)
    add("Magnitude", _magnitude(value), source)
    add("Size", _size(record.get(ObjectAttribute.SIZE)))

    if ObjectType.DOUBLE_STAR in obj.types or record.get(ObjectAttribute.COMPONENT):
        parts = [p.strip() for p in str(record.get(ObjectAttribute.COMPONENT, "")).split(",")]
        add("Component", parts[0])
        for candidate, origin in _candidates(obj, references):
            fields = [p.strip() for p in str(candidate.record.get(ObjectAttribute.COMPONENT, "")).split(",")]
            if len(fields) >= 2 and fields[1]:
                add("Separation", f"{fields[1]}″", origin)
                add("Position angle", f"{fields[2]}°" if len(fields) > 2 and fields[2] else "", origin)
                add("Measured in", fields[3] if len(fields) > 3 else "", origin)
                break

    if record.get(ObjectAttribute.RATING):
        add("Rating", _stars(record[ObjectAttribute.RATING]))
    if record.get(ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING):
        add("Binocular rating", _stars(record[ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING]))
    letters = str(record.get(ObjectAttribute.PROJECT_DOUBLE_STARS_LISTS, "")).upper()
    if letters:
        add("Double Stars lists", ", ".join(f"{DOUBLE_STAR_LISTS.get(c, c)} ({c})" for c in letters))
    if record.get(ObjectAttribute.RED_STARS_LIST) is True:
        add("Red star", "yes")
    add("DSS image", _dss(record.get(ObjectAttribute.DSS)))
    for key, text in ((ObjectAttribute.DISABLE_DSS, "no DSS image"),
                      (ObjectAttribute.DISABLE_WDS, "left out of the WDS"),
                      (ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS, "left out of the Double Stars project"),
                      (ObjectAttribute.PUBLISH_WITHOUT_OBSERVATION, "published without an observation")):
        if record.get(key) is True:
            add("Mark", text)
    if seen is not None:
        add("Seen", SEEN_TEXT.get(seen, seen.value))
    if references is not None:
        found = references.of(obj)
        add("References", "; ".join(f"{r.catalogue}: {r.label}" for r in found))
    add("Notes", record.get(ObjectAttribute.NOTES))
    add("Description", record.get(ObjectAttribute.DESCRIPTION))
    for key in sorted(record.keys() - _KNOWN):
        add(key, record[key])
    return facts


def _candidates(obj: Object, references: References | None) -> list[tuple[Object, str]]:
    """The Object, then its WDS reference if it has one (never any other catalogue's, see
    references.wds_reference), with the catalogue to name when it is not the Object itself.

    :param obj: the Object to start from
    :param references: the references to look the WDS one up in, or None for just the Object itself
    :returns: (candidate, catalogue to name it by, "" for `obj` itself)
    """
    wds = wds_reference(obj, references)
    return [(obj, ""), *([(wds, wds.catalogue)] if wds is not None else [])]


def _type_name(kind: ObjectType) -> str:
    return kind.name.replace("_", " ").capitalize()


def _coordinates(value: str) -> str:
    """`hhmmss.ss,±ddmmss.ss` as `16h 52m 41.40s, +36° 27′ 35.00″`; what is not in that format is given as it is.

    :param value: the raw COORDINATES value
    :returns: the formatted coordinates
    """
    match = COORDINATES_FORMAT.fullmatch(value)
    if match is None:
        return value
    ra_h, ra_m, ra_s, sign, dec_d, dec_m, dec_s = match.groups()
    return f"{ra_h}h {ra_m}m {ra_s}s, {sign}{dec_d}° {dec_m}′ {dec_s}″"


def _magnitude(value: str) -> str:
    """The parts (a double star has one for each component) separated by ` / `, the elements of a part by `, `.

    :param value: the raw MAGNITUDE value
    :returns: the formatted magnitude, or "" when `value` is empty
    """
    if not value:
        return ""
    parts = [p.strip() for p in normalize_magnitude(value).split(";")]
    return " / ".join(", ".join(e.strip() for e in part.split(",") if e.strip()) for part in parts if part)


def _size(value: Any) -> str:
    """`major,minor[,angle]` (arcminutes and degrees) as `8′ × 5′, position angle 164°`.

    :param value: the raw SIZE value
    :returns: the formatted size, or "" when `value` has no major axis
    """
    fields = [f.strip() for f in str(value or "").split(",")]
    if not fields[0]:
        return ""
    text = f"{fields[0]}′" + (f" × {fields[1]}′" if len(fields) > 1 and fields[1] else "")
    return text + (f", position angle {fields[2]}°" if len(fields) > 2 and fields[2] else "")


def _stars(value: Any) -> str:
    """A 0-3 rating as filled/empty star characters, e.g. "★★☆ (2 of 3)"; a value outside 0-3 is clamped,
    and one that is not a number is given as it is.

    :param value: the raw rating value
    :returns: the formatted rating, or "" when it clamps to 0
    """
    try:
        number = max(0, min(3, int(value)))
    except (TypeError, ValueError):
        return str(value)
    return "★" * number + "☆" * (3 - number) + f" ({number} of 3)" if number else ""


def _dss(value: Any) -> str:
    """`[survey][,field of view]` as `dss1, field of view 20′`.

    :param value: the raw DSS value
    :returns: the formatted DSS source, or "" when `value` is empty
    """
    fields = [f.strip() for f in str(value or "").split(",")]
    survey = fields[0] if fields and fields[0] else ""
    field = f"field of view {fields[1]}′" if len(fields) > 1 and fields[1] else ""
    return ", ".join(part for part in (survey, field) if part)
