"""The canonical text layout of catalogue files.

One record per line, indented by four spaces. Observations of a record go on lines of their
own, indented by eight; their German and English descriptions wrap onto continuation lines.
Attributes are written in canonical order, and unknown attributes are kept after the known
ones. Loading a file and rendering it again must give the identical text.
"""
import json
from typing import Any

from faint_fuzzies.domain.formats import normalize_magnitude
from faint_fuzzies.domain.model import (
    OBJECT_ATTRIBUTES,
    OBSERVATION_ATTRIBUTES,
    ObjectAttribute,
    ObjectType,
    ObservationAttribute,
)
from faint_fuzzies.domain.session import SESSION_ORDER, SessionAttribute

INTEGER_ATTRIBUTES = frozenset({ObjectAttribute.RATING, ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING})
BOOLEAN_ATTRIBUTES = frozenset({ObjectAttribute.RED_STARS_LIST, ObjectAttribute.DISABLE_DSS,
                                ObjectAttribute.DISABLE_WDS, ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS,
                                ObjectAttribute.PUBLISH_WITHOUT_OBSERVATION})
TYPE_ORDER = {t.value: position for position, t in enumerate(ObjectType)}


class LayoutError(ValueError):
    """A record cannot be rendered because an attribute has an unexpected value."""


def render_catalogue(records: list[dict[str, Any]]) -> str:
    """Renders a catalogue file's records in their canonical layout.

    :param records: the raw records to render, in the order they should appear in the file
    :returns: the file's text
    :raises LayoutError: when a record has an attribute with an unexpected value
    """
    lines = []
    for index, record in enumerate(records, start=1):
        try:
            lines.append(" " * 4 + _render_record(record))
        except LayoutError as exc:
            raise LayoutError(f"record {index}: {exc}") from exc
    return "[\n" + ",\n".join(lines) + "\n]\n"


def render_sessions(records: list[dict[str, Any]]) -> str:
    """The layout of the sessions file: a record starts on its own line with its short attributes, the long
    EQUIPMENT and DESCRIPTION (and any unknown attribute) follow on lines indented by eight, and the closing
    brace is on a line of its own. Empty attributes are left out; unknown ones are kept after the known ones.

    :param records: the raw session records to render, in the order they should appear in the file
    :returns: the file's text
    :raises LayoutError: when a record has an attribute with an unexpected value
    """
    lines = []
    for index, record in enumerate(records, start=1):
        try:
            lines.append(" " * 4 + _render_session(record))
        except LayoutError as exc:
            raise LayoutError(f"record {index}: {exc}") from exc
    return "[\n" + ",\n".join(lines) + "\n]\n"


LONG_SESSION_ATTRIBUTES = (SessionAttribute.EQUIPMENT, SessionAttribute.DESCRIPTION)


def _render_session(record: Any) -> str:
    """Renders one session record in its canonical layout.

    :param record: the raw record to render
    :returns: the record's text, without indentation
    :raises LayoutError: when the record is not an object, or a known attribute is not a string
    """
    if not isinstance(record, dict):
        raise LayoutError("record is not a JSON object")
    parts = []
    for key in _ordered_keys(record, SESSION_ORDER):
        value = record[key]
        if key in SESSION_ORDER:
            if not value:
                continue
            if not isinstance(value, str):
                raise LayoutError(f"{key} must be a string")
        text = f'"{key}": {json.dumps(value, ensure_ascii=False)}'
        parts.append("\n" + " " * 8 + text if key in LONG_SESSION_ATTRIBUTES or key not in SESSION_ORDER else text)
    if not parts:
        return "{}"
    return ("{" + ", ".join(parts) + "\n" + " " * 4 + "}").replace(" \n", "\n")


def _ordered_keys(data: dict[str, Any], known: tuple[str, ...]) -> list[str]:
    """`data`'s keys in canonical order: the known attributes first, in `known`'s order, then the rest in
    the order `data` already has them.

    :param data: the record whose keys to order
    :param known: the canonical order of its known attributes
    :returns: the ordered keys
    """
    return [k for k in known if k in data] + [k for k in data if k not in known]


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_record(record: Any) -> str:
    """Renders one object record in its canonical layout, without its surrounding indentation.

    :param record: the raw record to render
    :returns: the record's text
    :raises LayoutError: when the record is not an object, or an attribute has an unexpected value
    """
    if not isinstance(record, dict):
        raise LayoutError("record is not a JSON object")
    parts = []
    for key in _ordered_keys(record, OBJECT_ATTRIBUTES):
        value = record[key]
        if key not in OBJECT_ATTRIBUTES:
            parts.append(f'"{key}": {json.dumps(value, ensure_ascii=False)}')
        elif isinstance(value, bool) or value:
            parts.append(_render_attribute(key, value))
    return "{" + ", ".join(parts) + "}"


def _render_attribute(key: str, value: Any) -> str:
    """Renders one object attribute as its `"key": value` JSON text, in its canonical form.

    :param key: the attribute's name
    :param value: the attribute's raw value
    :returns: the rendered `"key": value` text
    :raises LayoutError: when the value is not of the type the attribute expects
    """
    if key == ObjectAttribute.OBSERVATIONS:
        if not isinstance(value, list):
            raise LayoutError("OBSERVATIONS must be a list")
        observations = ",\n".join(" " * 8 + _render_observation(o) for o in value)
        return f'"{key}": [\n{observations}\n' + " " * 4 + "]"
    if key in INTEGER_ATTRIBUTES:
        if isinstance(value, bool) or not isinstance(value, int):
            raise LayoutError(f"{key} must be an integer")
        return f'"{key}": {value}'
    if key in BOOLEAN_ATTRIBUTES:
        if not isinstance(value, bool):
            raise LayoutError(f"{key} must be true or false")
        return f'"{key}": {"true" if value else "false"}'
    if not isinstance(value, str):
        raise LayoutError(f"{key} must be a string")
    if key in (ObjectAttribute.NAME, ObjectAttribute.GROUP):
        return f'"{key}": {_string(", ".join(e.strip() for e in value.split(",")))}'
    if key == ObjectAttribute.TYPE:
        return f'"{key}": {_string(_canonical_types(value))}'
    if key == ObjectAttribute.MAGNITUDE:
        return f'"{key}": {_string(normalize_magnitude(value))}'
    return f'"{key}": {_string(value.strip())}'


def _canonical_types(value: str) -> str:
    """A TYPE value's codes, parsed and re-joined in their canonical order.

    :param value: the raw TYPE value
    :returns: the comma-separated codes in canonical order
    :raises LayoutError: when a code does not parse as an ObjectType
    """
    try:
        codes = [ObjectType.parse(code).value for code in value.split(",")]
    except ValueError as exc:
        raise LayoutError(f"TYPE: {exc}") from exc
    return ",".join(sorted(codes, key=TYPE_ORDER.__getitem__))


def _render_observation(observation: Any) -> str:
    """Renders one observation record in its canonical layout, with its description wrapped onto a
    continuation line.

    :param observation: the raw observation record to render
    :returns: the observation's text, without its surrounding indentation
    :raises LayoutError: when the record is not an object, or a known attribute is not a string
    """
    if not isinstance(observation, dict):
        raise LayoutError("observation is not a JSON object")
    parts: list[str] = []
    for key in _ordered_keys(observation, OBSERVATION_ATTRIBUTES):
        value = observation[key]
        if key not in OBSERVATION_ATTRIBUTES:
            parts.append(f'"{key}": {json.dumps(value, ensure_ascii=False)}')
            continue
        if not value:
            continue
        if not isinstance(value, str):
            raise LayoutError(f"observation {key} must be a string")
        prefix = ""
        if key == ObservationAttribute.DESCRIPTION_DE and parts:
            prefix = "\n" + " " * 12
        elif key == ObservationAttribute.DESCRIPTION_EN:
            prefix = "\n" + " " * (9 if len(parts) == 1 else 12)
        elif key not in (ObservationAttribute.DESCRIPTION, ObservationAttribute.DESCRIPTION_DE):
            value = value.replace(" ", "")
        parts.append(f'{prefix}"{key}": {_string(value)}')
    return ("{" + ", ".join(parts) + "}").replace(" \n", "\n")
