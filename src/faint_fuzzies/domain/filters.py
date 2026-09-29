"""Filtering Objects (and their Observations) by a FilterSpec: the shared engine behind the command line's
--filter, the app's Browse filters and anywhere else a subset of the collection needs picking out."""
from __future__ import annotations

import functools
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum, StrEnum
from typing import Any

from faint_fuzzies.domain.catalogue import Catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.findings import ERROR, INFO, WARNING
from faint_fuzzies.domain.lists import LISTS, ListDefinition, build_list
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType
from faint_fuzzies.domain.observation import (
    Color,
    Difficulty,
    FoundObservation,
    Grade,
    Method,
    Observation,
    OpticType,
    is_header,
)
from faint_fuzzies.domain.observer import OWN_ID, Observers, Scope
from faint_fuzzies.domain.references import References
from faint_fuzzies.domain.seen import SeenStatus, seen_status
from faint_fuzzies.finding_index import FindingIndex


class FilterKey(StrEnum):
    """A FilterSpec criterion's name, exactly as given in its JSON form and as FilterSpec's own field name."""
    NAME = "name"
    GROUP = "group"
    NAME_GROUP = "name_group"
    CONSTELLATION = "constellation"
    OBSERVER = "observer"
    CATALOGUE = "catalogue"
    SESSION = "session"
    NAME_PATTERN = "name_pattern"
    GROUP_PATTERN = "group_pattern"
    NAME_GROUP_PATTERN = "name_group_pattern"
    CONSTELLATION_PATTERN = "constellation_pattern"
    TYPE = "type"
    TYPE_EXCLUDE = "type_exclude"
    PROJECT = "project"
    IS_GROUP = "is_group"
    EXCLUDE_GROUP_MEMBERS = "exclude_group_members"
    PUBLIC = "public"
    HAS_SKETCH = "has_sketch"
    HAS_PHOTOGRAPH = "has_photograph"
    HAS_IMAGE = "has_image"
    HAS_NOTES = "has_notes"
    FOLLOW_REFERENCES = "follow_references"
    HEADER_ONLY = "header_only"
    PUBLISH_WITHOUT_OBSERVATION = "publish_without_observation"
    APERTURE = "aperture"
    PRIVATE_GRADE = "private_grade"
    DATE = "date"
    SIZE_RATIO = "size_ratio"
    SEPARATION = "separation"
    RATING = "rating"
    BINOCULAR_RATING = "binocular_rating"
    SEEN = "seen"
    OPTIC_TYPE = "optic_type"
    PUBLIC_GRADE = "public_grade"
    METHOD = "method"
    FINDING = "finding"
    SCOPE = "scope"
    MAGNITUDE = "magnitude"
    MAGNITUDE_DELTA = "magnitude_delta"
    SIZE = "size"


TEXT_CRITERIA = (FilterKey.NAME, FilterKey.GROUP, FilterKey.NAME_GROUP, FilterKey.CONSTELLATION, FilterKey.OBSERVER,
                 FilterKey.CATALOGUE, FilterKey.SESSION)
PATTERN_CRITERIA = (FilterKey.NAME_PATTERN, FilterKey.GROUP_PATTERN, FilterKey.NAME_GROUP_PATTERN,
                   FilterKey.CONSTELLATION_PATTERN)
TYPE_CRITERIA = (FilterKey.TYPE, FilterKey.TYPE_EXCLUDE)
PROJECT_CRITERIA = (FilterKey.PROJECT,)
FLAG_CRITERIA = (FilterKey.IS_GROUP, FilterKey.EXCLUDE_GROUP_MEMBERS, FilterKey.PUBLIC, FilterKey.HAS_SKETCH,
                 FilterKey.HAS_PHOTOGRAPH, FilterKey.HAS_IMAGE, FilterKey.HAS_NOTES, FilterKey.FOLLOW_REFERENCES,
                 FilterKey.HEADER_ONLY, FilterKey.PUBLISH_WITHOUT_OBSERVATION)
RANGE_CRITERIA = (FilterKey.APERTURE, FilterKey.PRIVATE_GRADE, FilterKey.DATE, FilterKey.SIZE_RATIO,
                  FilterKey.SEPARATION, FilterKey.RATING, FilterKey.BINOCULAR_RATING)
CHOICE_CRITERIA = (FilterKey.SEEN, FilterKey.OPTIC_TYPE, FilterKey.PUBLIC_GRADE, FilterKey.METHOD,
                   FilterKey.FINDING, FilterKey.SCOPE)
SUPPORTED = (*TEXT_CRITERIA, *PATTERN_CRITERIA, *TYPE_CRITERIA, *PROJECT_CRITERIA, *FLAG_CRITERIA,
             *RANGE_CRITERIA, *CHOICE_CRITERIA, FilterKey.MAGNITUDE, FilterKey.MAGNITUDE_DELTA, FilterKey.SIZE)

Range = tuple[Any, Any]  # inclusive bounds; None leaves that side open
MAGNITUDE_BANDS = ("v", "b", "p")  # visual, blue/photographic, a GCVS-style photographic value
SIZE_AXES = ("major", "minor")


class FilterSpecError(ValueError):
    """The filter specification is not valid."""


@dataclass(frozen=True)
class MagnitudeCriterion:
    """A magnitude range, and optionally which of an Object's several possible MAGNITUDE values it applies to.

    :ivar range: the inclusive magnitude bounds
    :ivar band: one of MAGNITUDE_BANDS, or None for the same visual > blue > first priority
        :func:`_object_magnitudes` always used before band selection existed
    """
    range: Range
    band: str | None = None


@dataclass(frozen=True)
class SizeCriterion:
    """A size range, and optionally which of an Object's SIZE dimensions it applies to.

    :ivar range: the inclusive size bounds, in arcminutes
    :ivar axis: one of SIZE_AXES, or None for the smaller of the major and minor diameters (major is never
        smaller than minor, so this is what decides whether an Object is at least a given size in every
        direction, not just the major axis). An Object with no minor of its own is treated as circular - its
        major stands in for both - for None and "major"; "major" alone is the size criterion's original,
        pre-axis behavior. "minor" alone excludes such an Object outright, since there is then nothing to
        check against it.
    """
    range: Range
    axis: str | None = None


@dataclass(frozen=True)
class FilterSpec:
    """Criteria are combined with AND; several values inside one criterion mean OR. The observation criteria
    (observer, method, public, optic_type, aperture, date, has_sketch, has_photograph, has_image, public_grade,
    private_grade, session, scope) must all hold for the same observation.

    :ivar name: Object names to match (OR), case-insensitive, against any of an Object's own names
    :ivar group: Object group names to match (OR), the same way as `name`
    :ivar name_group: values to match (OR), case-insensitive, against any of an Object's names or
        groups - for an exact value that should find a match whether the Object turns out to be a Group
        or a pair with no Group of its own
    :ivar constellation: constellations to match (OR), case-insensitive
    :ivar observer: ids from the observers file; the owner's own observations match the id of whichever
        observer has scope OWNER (see :func:`filter_objects`)
    :ivar catalogue: catalogue names, as the results show them
    :ivar session: the ISO start of a Session (as "session" is shown on an observation); matches
        observations that Session contains, the same as --sessions assigns them
    :ivar name_pattern: regular expressions that must fully match one of an Object's names (OR)
    :ivar group_pattern: regular expressions that must fully match one of an Object's groups (OR)
    :ivar name_group_pattern: regular expressions that must fully match one of an Object's names or
        groups (OR) - for a pattern that should find a match whichever it turns out to be, a Group or a
        pair with no Group of its own, without needing name_pattern and group_pattern both given and
        both satisfied (criteria still combine with AND, same as every other one)
    :ivar constellation_pattern: regular expressions that must fully match the Object's constellation
    :ivar type: Object types the Object must have at least one of (OR)
    :ivar type_exclude: Object types the Object must have none of
    :ivar project: the name of a list (global, project-double-stars, project-deep-sky-with-binoculars);
        matches an Object exactly when it would appear in that list: its own entry, a group's members, or
        the same system under another catalogue
    :ivar is_group: whether the Object must (True) or must not (False) be a group
    :ivar exclude_group_members: whether to leave out a double star pair that is a member of a matched group
    :ivar seen: the Object's seen status (OR)
    :ivar public: an observation's public flag (observation criterion)
    :ivar optic_type: an observation's optic type (observation criterion, OR)
    :ivar method: an observation's method (observation criterion, OR)
    :ivar aperture: an observation's optic aperture, in range (observation criterion)
    :ivar date: an observation's date, in range (observation criterion)
    :ivar has_sketch: whether an observation has a sketch (observation criterion)
    :ivar has_photograph: whether an observation has a photograph (observation criterion)
    :ivar has_image: whether an observation has an image (observation criterion)
    :ivar follow_references: whether the observations of the Objects that an Object references in the other
        catalogues count as its own for the observation criteria and for the seen status
    :ivar public_grade: an observation's Public Grade (Difficulty or Color) result (observation criterion, OR)
    :ivar private_grade: an observation's Private Grade result, in range (observation criterion)
    :ivar size_ratio: the major over the minor diameter of the Object's SIZE, in range (an Object without
        both diameters never matches)
    :ivar finding: the level of an Object - "error", "warning" or "info": the worst of its Findings and of
        those of its Observations, so an Object matches exactly one of them and an Invalid Object is always
        an "error"; needs the Findings of a loaded data directory
    :ivar header_only: whether the Object has a Header but is not published, since its Global-list entry has
        no valid Observation and the mark `publish_without_observation` does not count as one
    :ivar publish_without_observation: the `publish_without_observation` mark on the record itself
    :ivar magnitude: the Object's magnitude(s), in range (see MagnitudeCriterion); always read through the
        reference when the Object itself has none (a double star's own catalogue record usually has none at
        all). Every component matters, not just the first: a double star has one magnitude per star
        ("primary;secondary" in the record), and all of them must be in range - "brighter than 8" with a 7.5
        primary but an 11 secondary does not qualify (see :func:`_object_magnitudes`)
    :ivar magnitude_delta: the same shape as `magnitude` (a MagnitudeCriterion, band included) applied to a
        double star's absolute magnitude difference, abs(primary - secondary), instead of either value on
        its own; an Object without exactly two magnitude components (anything that is not a double star, or
        a double star whose record gives only one) never matches it, since there is then no difference to
        compute
    :ivar size: the Object's SIZE, in range, in arcminutes (see SizeCriterion); never resolved through a
        reference (unlike separation, SIZE is normally an Object's own)
    :ivar separation: a double star's separation in arcseconds, resolved through the reference (usually the
        WDS) the same way as `magnitude`
    :ivar rating: the record's own RATING - the Object's general Rating (see CONTEXT.md), in range
    :ivar binocular_rating: the record's own PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING, in range - a distinct,
        independently stored rating, not the same concept as `rating` read a second way
    :ivar has_notes: whether the Object's record has a non-empty NOTES (a private remark, not DESCRIPTION,
        which is public-facing text)
    :ivar scope: an observation's Observer Scope (observation criterion, OR): an Observation with no Observer
        (the owner's own) is OWNER, the same convention `observer` already uses for it
    """
    name: tuple[str, ...] = ()
    group: tuple[str, ...] = ()
    name_group: tuple[str, ...] = ()
    constellation: tuple[str, ...] = ()
    observer: tuple[str, ...] = ()
    catalogue: tuple[str, ...] = ()
    session: tuple[str, ...] = ()
    name_pattern: tuple[str, ...] = ()
    group_pattern: tuple[str, ...] = ()
    name_group_pattern: tuple[str, ...] = ()
    constellation_pattern: tuple[str, ...] = ()
    type: tuple[ObjectType, ...] = ()
    type_exclude: tuple[ObjectType, ...] = ()
    project: tuple[str, ...] = ()
    is_group: bool | None = None
    exclude_group_members: bool = False
    seen: tuple[SeenStatus, ...] = ()
    public: bool | None = None
    optic_type: tuple[OpticType, ...] = ()
    method: tuple[Method, ...] = ()
    aperture: Range | None = None
    date: Range | None = None
    has_sketch: bool | None = None
    has_photograph: bool | None = None
    has_image: bool | None = None
    follow_references: bool = False
    public_grade: tuple[Difficulty | Color, ...] = ()
    private_grade: Range | None = None
    size_ratio: Range | None = None
    finding: tuple[str, ...] = ()
    header_only: bool | None = None
    publish_without_observation: bool | None = None
    magnitude: MagnitudeCriterion | None = None
    magnitude_delta: MagnitudeCriterion | None = None
    size: SizeCriterion | None = None
    separation: Range | None = None
    rating: Range | None = None
    binocular_rating: Range | None = None
    has_notes: bool | None = None
    scope: tuple[Scope, ...] = ()

    @property
    def has_observation_criteria(self) -> bool:
        """Whether any criterion that must hold for the same observation is set (see the class docstring)."""
        return any((self.observer, self.method, self.public is not None, self.optic_type, self.aperture, self.date,
                    self.has_sketch is not None, self.has_photograph is not None, self.has_image is not None,
                    self.public_grade, self.private_grade, self.session, self.scope))

    @classmethod
    def from_dict(cls, data: Any) -> FilterSpec:
        """Parses a filter specification from its JSON form (a dict of criterion name -> value, each as the
        class docstring describes it).

        :param data: the parsed JSON object
        :returns: the parsed specification
        :raises FilterSpecError: when `data` is not an object, has an unknown key, or a value does not match
            its criterion's expected shape
        """
        if not isinstance(data, dict):
            raise FilterSpecError("a filter specification must be a JSON object")
        unknown = sorted(data.keys() - set(SUPPORTED))
        if unknown:
            raise FilterSpecError(f"unknown filter key '{unknown[0]}' (supported: {', '.join(SUPPORTED)})")

        values: dict[str, Any] = {}
        for key in (*TEXT_CRITERIA, *PATTERN_CRITERIA):
            if key in data:
                values[key] = _text_list(key, data[key])
        for key in PATTERN_CRITERIA:
            for pattern in values.get(key, ()):
                _compile(key, pattern)
        for key in TYPE_CRITERIA:
            if key in data:
                values[key] = _choices(key, _text_list(key, data[key]), ObjectType.parse)
        if FilterKey.PROJECT in data:
            values[FilterKey.PROJECT] = _choices(FilterKey.PROJECT, _text_list(FilterKey.PROJECT,
                                                 data[FilterKey.PROJECT]), _project_name)
        if FilterKey.SEEN in data:
            values[FilterKey.SEEN] = _choices(FilterKey.SEEN, _text_list(FilterKey.SEEN, data[FilterKey.SEEN]),
                                              _by_value(SeenStatus))
        if FilterKey.OPTIC_TYPE in data:
            values[FilterKey.OPTIC_TYPE] = _choices(FilterKey.OPTIC_TYPE,
                                                    _text_list(FilterKey.OPTIC_TYPE, data[FilterKey.OPTIC_TYPE]),
                                                    _by_value(OpticType))
        if FilterKey.METHOD in data:
            values[FilterKey.METHOD] = _choices(FilterKey.METHOD, _text_list(FilterKey.METHOD,
                                                data[FilterKey.METHOD]), _by_value(Method))
        if FilterKey.FINDING in data:
            values[FilterKey.FINDING] = _choices(FilterKey.FINDING, _text_list(FilterKey.FINDING,
                                                 data[FilterKey.FINDING]), _finding_level)
        if FilterKey.PUBLIC_GRADE in data:
            values[FilterKey.PUBLIC_GRADE] = _choices(FilterKey.PUBLIC_GRADE,
                                                       _text_list(FilterKey.PUBLIC_GRADE, data[FilterKey.PUBLIC_GRADE]),
                                                       _public_grade)
        if FilterKey.SCOPE in data:
            values[FilterKey.SCOPE] = _choices(FilterKey.SCOPE, _text_list(FilterKey.SCOPE, data[FilterKey.SCOPE]),
                                               _by_value(Scope))
        for key in FLAG_CRITERIA:
            if key in data:
                if not isinstance(data[key], bool):
                    raise FilterSpecError(f"'{key}' must be true or false")
                values[key] = data[key]
        for key in RANGE_CRITERIA:
            if key in data:
                values[key] = _range(key, data[key], _iso_date if key == FilterKey.DATE else _number)
        if FilterKey.MAGNITUDE in data:
            values[FilterKey.MAGNITUDE] = _magnitude_criterion(data[FilterKey.MAGNITUDE])
        if FilterKey.MAGNITUDE_DELTA in data:
            values[FilterKey.MAGNITUDE_DELTA] = _range_with_selector(
                FilterKey.MAGNITUDE_DELTA, data[FilterKey.MAGNITUDE_DELTA], "band", MAGNITUDE_BANDS,
                MagnitudeCriterion)
        if FilterKey.SIZE in data:
            values[FilterKey.SIZE] = _size_criterion(data[FilterKey.SIZE])
        return cls(**values)


def _text_list(key: str, value: Any) -> tuple[str, ...]:
    """A single string or a list of strings, normalized to a tuple.

    :param key: the criterion's name, for the error message
    :param value: the raw JSON value
    :returns: `value` as a tuple of strings
    :raises FilterSpecError: when `value` is neither a string nor a list of strings
    """
    items = value if isinstance(value, list) else [value]
    if not all(isinstance(item, str) for item in items):
        raise FilterSpecError(f"'{key}' must be a string or a list of strings")
    return tuple(items)


def _choices(key: str, texts: tuple[str, ...], parse: Callable[[str], Any]) -> tuple[Any, ...]:
    """Parses each of `texts` with `parse`, turning a ValueError into a FilterSpecError named after `key`.

    :param key: the criterion's name, for the error message
    :param texts: the raw text values to parse
    :param parse: parses one text value, raising ValueError when it is not a known choice
    :returns: the parsed values
    :raises FilterSpecError: when `parse` rejects any of `texts`
    """
    try:
        return tuple(parse(text) for text in texts)
    except ValueError as exc:
        raise FilterSpecError(f"'{key}': {exc}") from exc


def _by_value(enum: type[Enum]) -> Callable[[str], Any]:
    """A parser that looks `text` up by `enum`'s member values, case-insensitively.

    :param enum: the enum to parse members of
    :returns: a parser raising ValueError when `text` matches no member's value
    """
    def parse(text: str) -> Any:
        for member in enum:
            if member.value.casefold() == text.strip().casefold():
                return member
        choices = ", ".join(m.value for m in enum)
        raise ValueError(f"unknown value '{text}' (choose from {choices})")
    return parse


def _finding_level(text: str) -> str:
    """Parses a `finding` criterion value (one of ERROR, WARNING, INFO).

    :param text: the raw text value
    :returns: the matched level
    :raises ValueError: when `text` matches none of them
    """
    for level in (ERROR, WARNING, INFO):
        if level == text.strip().casefold():
            return level
    raise ValueError(f"unknown value '{text}' (choose from {ERROR}, {WARNING}, {INFO})")


def _project_name(text: str) -> str:
    """Parses a `project` criterion value against the names in LISTS, case-insensitively.

    :param text: the raw text value
    :returns: the matched list name, as LISTS spells it
    :raises ValueError: when `text` matches no list name
    """
    for name in LISTS:
        if name.casefold() == text.strip().casefold():
            return name
    raise ValueError(f"unknown project '{text}' (choose from {', '.join(LISTS)})")


def _public_grade(text: str) -> Difficulty | Color:
    """Parses a `public_grade` criterion value against both the Difficulty and Color enums.

    :param text: the raw text value
    :returns: the matched Difficulty or Color member
    :raises ValueError: when `text` matches neither enum
    """
    for enum in (Difficulty, Color):
        if text.strip().upper() in enum.__members__:
            return enum[text.strip().upper()]
    raise ValueError(f"unknown value '{text}' (choose from EASY, MEDIUM, HARD, FAILED, RED, ORANGE)")


def _compile(key: str, pattern: str) -> re.Pattern[str]:
    """Compiles a `_pattern` criterion's regular expression, case-insensitively.

    :param key: the criterion's name, for the error message
    :param pattern: the raw regular expression text
    :returns: the compiled pattern
    :raises FilterSpecError: when `pattern` is not a valid regular expression
    """
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise FilterSpecError(f"'{key}': invalid regular expression '{pattern}': {exc}") from exc


def _number(text: Any) -> float:
    """A range bound that must be a plain number (not a bool, which is technically an int).

    :param text: the raw JSON value
    :returns: `text` unchanged
    :raises TypeError: when `text` is not a number
    """
    if isinstance(text, bool) or not isinstance(text, (int, float)):
        raise TypeError("a number")
    return text


def _iso_date(text: Any) -> date:
    """A range bound that must be an ISO date string.

    :param text: the raw JSON value
    :returns: the parsed date
    :raises TypeError: when `text` is not a string
    :raises ValueError: when `text` is not a valid ISO date
    """
    if not isinstance(text, str):
        raise TypeError("a date such as 2020-01-31")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("a date such as 2020-01-31") from exc


def _range(key: str, value: Any, parse: Callable[[Any], Any]) -> Range:
    """A `[min, max]` JSON value, each bound either null (open) or parsed with `parse`.

    :param key: the criterion's name, for the error message
    :param value: the raw JSON value
    :param parse: parses one non-null bound, raising ValueError or TypeError when it is invalid
    :returns: the two bounds, each None or parsed
    :raises FilterSpecError: when `value` is not a two-element list, a bound is invalid, or the lower bound
        is above the upper bound
    """
    if not isinstance(value, list) or len(value) != 2:
        raise FilterSpecError(f"'{key}' must be a list of two bounds, null leaving a side open")
    bounds = []
    for bound in value:
        try:
            bounds.append(None if bound is None else parse(bound))
        except (ValueError, TypeError) as exc:
            raise FilterSpecError(f"'{key}': each bound must be null or {exc}") from exc
    if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
        raise FilterSpecError(f"'{key}': the lower bound is above the upper bound")
    return bounds[0], bounds[1]


def _range_with_selector(key: str, value: Any, selector: str, choices: tuple[str, ...],
                         make: Callable[[Range, str | None], Any]) -> Any:
    """A plain `[min, max]` range, or `{"range": [min, max], <selector>: one of choices}` - shared by
    _magnitude_criterion and _size_criterion, whose JSON shapes and validation only differ in the selector's
    name and choices.

    :param key: the criterion's name, for the error message
    :param value: the raw JSON value
    :param selector: the selector key's name ("band" or "axis")
    :param choices: the selector's allowed values
    :param make: builds the result from the parsed range and the selected choice (or None)
    :returns: `make`'s result
    :raises FilterSpecError: when `value` does not match either shape, has an unknown key, or the selector's
        value is not one of `choices`
    """
    if isinstance(value, list):
        return make(_range(key, value, _number), None)
    if not isinstance(value, dict) or "range" not in value:
        raise FilterSpecError(
            f"'{key}' must be a list of two bounds, or an object with 'range' and optionally '{selector}'"
        )
    extra = set(value) - {"range", selector}
    if extra:
        raise FilterSpecError(f"'{key}' has an unknown key '{min(extra)}' (choose from range, {selector})")
    selected = value.get(selector)
    if selected is not None:
        if not isinstance(selected, str) or selected.strip().casefold() not in choices:
            raise FilterSpecError(f"'{key}.{selector}' must be one of {', '.join(choices)}")
        selected = selected.strip().casefold()
    return make(_range(key, value["range"], _number), selected)


def _magnitude_criterion(value: Any) -> MagnitudeCriterion:
    return _range_with_selector(FilterKey.MAGNITUDE, value, "band", MAGNITUDE_BANDS, MagnitudeCriterion)


def _size_criterion(value: Any) -> SizeCriterion:
    return _range_with_selector(FilterKey.SIZE, value, "axis", SIZE_AXES, SizeCriterion)


_CACHE_DISABLED = os.environ.get("FAINT_FUZZIES_DISABLE_FILTER_CACHE") == "1"
"""Set FAINT_FUZZIES_DISABLE_FILTER_CACHE=1 to force the pre-caching full-scan behavior, for comparing
the app's responsiveness with and without it by hand (see the README's Filter specification) - not read
anywhere else, and not a supported setting: a manual developer tool that may change or disappear without
notice."""


@dataclass(frozen=True)
class Match:
    """An Object and the observations that matched (all of them when the filter has no observation criteria).

    :ivar object: the matched Object
    :ivar observations: the matched observations
    :ivar seen: the seen status, judged from the Object's observations plus the referenced ones with
        follow_references
    """
    object: Object
    observations: tuple[FoundObservation, ...]
    seen: SeenStatus


def _candidate_catalogues(collection: Collection, spec: FilterSpec) -> list[Catalogue]:
    """The catalogues `spec.catalogue` restricts the search to, in collection order - every catalogue when
    it gives none. A catalogue's Objects are already contiguous (see Collection.__init__, which builds
    `collection.objects` by extending one catalogue's list after another), so scanning only these catalogues
    needs no per-object check at all - unlike every other criterion, `catalogue` can be resolved before the
    per-object loop even starts.

    :param collection: the collection to search
    :param spec: the criteria to filter by
    :returns: the matching catalogues
    """
    if not spec.catalogue:
        return collection.catalogues
    wanted = {c.casefold() for c in spec.catalogue}
    return [c for c in collection.catalogues if c.name.casefold() in wanted]


def _indexed_candidates(collection: Collection, spec: FilterSpec,
                        catalogues: list[Catalogue]) -> tuple[Object, ...] | None:
    """The Objects to visit instead of scanning `catalogues` in full, when exactly one of `name`, `type` or
    `constellation` is given a single value: Collection keeps each of those indexed, already in collection
    order (see objects_by_name, objects_by_type, objects_by_constellation), so the smallest matching index
    can drive the loop directly instead of visiting every Object to ask. object_matches still checks every
    criterion, this one included, on each candidate - a wrong or incomplete index could only make this
    slower, never wrong. None when no such criterion applies (every one of the three is unset, or given more
    than one value), since concatenating several keys' lists would not preserve collection order the way one
    key's list already does.

    :param collection: the collection to search
    :param spec: the criteria to filter by
    :param catalogues: the catalogues `_candidate_catalogues` has already restricted the search to
    :returns: the candidate Objects, in collection order, or None to fall back to a full per-catalogue scan
    """
    if _CACHE_DISABLED:
        return None
    options = []
    if len(spec.name) == 1:
        options.append(collection.objects_by_name(spec.name[0].casefold()))
    if len(spec.type) == 1:
        options.append(collection.objects_by_type(spec.type[0]))
    if len(spec.constellation) == 1:
        options.append(collection.objects_by_constellation(spec.constellation[0].casefold()))
    if not options:
        return None
    smallest = min(options, key=len)
    if len(catalogues) == len(collection.catalogues):
        return smallest
    wanted = {c.name for c in catalogues}
    return tuple(obj for obj in smallest if obj.catalogue in wanted)


def filter_objects(collection: Collection, spec: FilterSpec, references: References,
                   observers: Observers | None = None, findings: FindingIndex | None = None) -> list[Match]:
    """Filters all the Objects of the collection, in the order of its catalogues. Invalid Objects are not in
    the collection, see :func:`invalid_objects`.

    :param collection: the collection to filter
    :param spec: the criteria to filter by
    :param references: resolves an Object's references for follow_references and the criteria that read
        through a reference (magnitude, magnitude_delta, separation)
    :param observers: resolves the id of an observation with none (the owner's own) for the `observer`
        criterion; without it, the neutral OWN_ID placeholder is used instead of the owner's real id
    :param findings: the Findings of a loaded data directory, needed by the `finding` criterion
    :returns: the matching Objects with their matched observations
    """
    wanted_observers = {o.casefold() for o in spec.observer}
    methods = {m.value for m in spec.method}
    sessions = {s.casefold() for s in spec.session}
    object_matches = _object_predicate(collection, spec, references, observers, findings)

    def candidates(_obj: Object) -> tuple[FoundObservation, ...]:
        _found = tuple(FoundObservation(o, _obj) for o in _obj.all_observations)
        if spec.follow_references:
            _found += tuple(FoundObservation(o, other)
                           for other in references.of(_obj) for o in other.all_observations)
        return _found

    owner_id = observers.owner_id() if observers else OWN_ID

    def observation_matches(o: Observation) -> bool:
        if wanted_observers and (o.observer.id if o.observer else owner_id).casefold() not in wanted_observers:
            return False
        if methods and o.method not in methods:
            return False
        if spec.public is not None and o.public != spec.public:
            return False
        if spec.optic_type and (o.optic is None or o.optic.type not in spec.optic_type):
            return False
        if spec.aperture and not _in_range(o.optic.aperture if o.optic else None, spec.aperture):
            return False
        if spec.date and not _in_range(o.start.date() if o.start else None, spec.date):
            return False
        if spec.has_sketch is not None and o.has_sketch != spec.has_sketch:
            return False
        if spec.has_photograph is not None and o.has_photograph != spec.has_photograph:
            return False
        if spec.has_image is not None and o.has_image != spec.has_image:
            return False
        if spec.public_grade and not any(e.result in spec.public_grade for e in o.visibility):
            return False
        if spec.private_grade and not any(isinstance(e.result, Grade) and _in_range(e.result.low, spec.private_grade)
                                  for e in o.visibility):
            return False
        if sessions and (o.session is None or o.session.start.isoformat(timespec="minutes").casefold() not in sessions):
            return False
        return not spec.scope or (o.observer.scope if o.observer else Scope.OWNER) in spec.scope

    catalogues = _candidate_catalogues(collection, spec)
    driver = _indexed_candidates(collection, spec, catalogues)
    objects = driver if driver is not None else (obj for catalogue in catalogues for obj in catalogue.objects)
    matches = []
    for obj in objects:
        if not object_matches(obj):
            continue
        found = candidates(obj)
        status = seen_status(obj, [f.observation for f in found])
        if spec.seen and status not in spec.seen:
            continue
        if spec.has_observation_criteria:
            found = tuple(f for f in found if observation_matches(f.observation))
            if not found:
                continue
        matches.append(Match(obj, found, status))
    return matches


def _object_predicate(collection: Collection, spec: FilterSpec, references: References, observers: Observers | None,
                      findings: FindingIndex | None) -> Callable[[Object], bool]:
    """Builds a predicate for whether an Object meets the criteria about the Object itself (those about its
    Observations are another matter, see filter_objects).

    :param collection: the collection the Object belongs to
    :param spec: the criteria to check
    :param references: resolves an Object's references for the criteria that read through one
    :param observers: resolves the `project` criterion's lists
    :param findings: the Findings of a loaded data directory, needed by the `finding` criterion
    :returns: a predicate, Object -> whether it matches - the `catalogue` criterion is not checked here, since
        both callers already only ever pass it Objects of a matching catalogue (see
        :func:`_candidate_catalogues`)
    :raises FilterSpecError: when `spec.finding` is set but `findings` is None
    """
    names = {n.casefold() for n in spec.name}
    groups = {g.casefold() for g in spec.group}
    name_groups = {n.casefold() for n in spec.name_group}
    constellations = {c.casefold() for c in spec.constellation}
    name_patterns = [_compile("name_pattern", p) for p in spec.name_pattern]
    group_patterns = [_compile("group_pattern", p) for p in spec.group_pattern]
    name_group_patterns = [_compile("name_group_pattern", p) for p in spec.name_group_pattern]
    constellation_patterns = [_compile("constellation_pattern", p) for p in spec.constellation_pattern]
    project_ids = _project_object_ids(collection, references, spec.project, observers) if spec.project else None
    if spec.finding and findings is None:
        raise FilterSpecError("'finding' needs a data directory: the findings are made when one is loaded")
    published = (_project_object_ids(collection, references, ("global",), observers)
                 if spec.header_only is not None else frozenset())

    def object_matches(obj: Object) -> bool:
        if project_ids is not None and id(obj) not in project_ids:
            return False
        if names and not any(n.casefold() in names for n in obj.names):
            return False
        if groups and not any(g.casefold() in groups for g in obj.groups):
            return False
        if name_groups and not (any(n.casefold() in name_groups for n in obj.names)
                               or any(g.casefold() in name_groups for g in obj.groups)):
            return False
        if name_patterns and not _any_full_match(name_patterns, obj.names):
            return False
        if group_patterns and not _any_full_match(group_patterns, obj.groups):
            return False
        if name_group_patterns and not (_any_full_match(name_group_patterns, obj.names)
                                       or _any_full_match(name_group_patterns, obj.groups)):
            return False
        if spec.type and not any(t in spec.type for t in obj.types):
            return False
        if spec.type_exclude and any(t in spec.type_exclude for t in obj.types):
            return False
        if constellations and obj.constellation.casefold() not in constellations:
            return False
        if constellation_patterns and not _any_full_match(constellation_patterns, (obj.constellation,)):
            return False
        if spec.is_group is not None and obj.is_group != spec.is_group:
            return False
        if spec.size_ratio and not _in_range(obj.size_ratio, spec.size_ratio):
            return False
        if spec.size and not _in_range(_object_size(obj, spec.size.axis), spec.size.range):
            return False
        if spec.separation and not _in_range(_object_separation(obj, references), spec.separation):
            return False
        if spec.magnitude:
            values = _object_magnitudes(obj, references, spec.magnitude.band)
            if not values or not all(_in_range(v, spec.magnitude.range) for v in values):
                return False
        if spec.magnitude_delta:
            values = _object_magnitudes(obj, references, spec.magnitude_delta.band)
            delta = abs(values[0] - values[1]) if len(values) == 2 else None
            if not _in_range(delta, spec.magnitude_delta.range):
                return False
        if spec.rating and not _in_range(_record_number(obj, ObjectAttribute.RATING), spec.rating):
            return False
        if spec.binocular_rating and not _in_range(
                _record_number(obj, ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING), spec.binocular_rating):
            return False
        if (spec.has_notes is not None
                and bool(str(obj.record.get(ObjectAttribute.NOTES, "")).strip()) != spec.has_notes):
            return False
        if spec.exclude_group_members and _is_double_star_group_member(obj, collection.group_names(obj.rank)):
            return False
        if spec.finding:
            assert findings is not None  # guaranteed above: a FilterSpecError is raised otherwise
            if findings.severity(obj) not in spec.finding:
                return False
        if spec.header_only is not None:
            header_only = obj.valid and id(obj) not in published and any(is_header(o) for o in obj.observations)
            if header_only != spec.header_only:
                return False
        return (spec.publish_without_observation is None
                or obj.publish_without_observation == spec.publish_without_observation)

    return object_matches


def invalid_objects(collection: Collection, spec: FilterSpec, references: References,
                    observers: Observers | None = None, findings: FindingIndex | None = None) -> list[Object]:
    """The Invalid Objects that meet the criteria about the Object itself, in the order of the catalogues. They have no
    Observations, no Seen status and no Session, so a criterion about any of those leaves none.

    :param collection: the collection to filter
    :param spec: the criteria to filter by
    :param references: resolves an Object's references for the criteria that read through one
    :param observers: resolves the `project` criterion's lists
    :param findings: the Findings of a loaded data directory, needed by the `finding` criterion
    :returns: the matching Invalid Objects
    """
    if spec.has_observation_criteria or spec.seen or spec.project or spec.session:
        return []
    matches = _object_predicate(collection, spec, references, observers, findings)
    return [obj for catalogue in _candidate_catalogues(collection, spec) for obj in catalogue.invalid if matches(obj)]


def _project_object_ids(collection: Collection, references: References, projects: tuple[str, ...],
                        observers: Observers | None) -> frozenset[int]:
    """The ids of the Objects that belong to any of the named lists: an entry's unit, its group members
    (the pairs of a double star group) and the raw objects (of every catalogue) whose observations feed it.
    Each list is built at most once per Collection, via Collection.cached_object_ids, instead of once per
    filter evaluation that needs it.

    :param collection: the collection the lists belong to
    :param references: resolves the lists' references
    :param projects: the list names to collect ids from
    :param observers: resolves the lists' observers
    :returns: the ids (id(Object)) of every Object belonging to any of `projects`
    """
    ids: set[int] = set()
    for name in projects:
        build = functools.partial(_list_entry_ids, LISTS[name], collection, references, observers)
        ids |= build() if _CACHE_DISABLED else collection.cached_object_ids(name, build)
    return frozenset(ids)


def _list_entry_ids(definition: ListDefinition, collection: Collection, references: References,
                    observers: Observers | None) -> frozenset[int]:
    """The ids of the Objects one list's entries collect: an entry's unit, its group members and the raw
    objects whose observations feed it.

    :param definition: the list to build (a value of LISTS)
    :param collection: the collection to build the list from
    :param references: resolves the list's references
    :param observers: resolves the list's observers
    :returns: the ids (id(Object)) of every Object the list's entries collect
    """
    result = build_list(definition, collection, references, observers)
    ids: set[int] = set()
    for entry in result.entries:
        ids.add(id(entry.unit))
        ids.update(id(m) for m in entry.members)
        ids.update(id(o) for o in entry.contributors)
    return frozenset(ids)


def _any_full_match(patterns: list[re.Pattern[str]], texts: tuple[str, ...]) -> bool:
    return any(p.fullmatch(t) for p in patterns for t in texts)


def _in_range(value: Any, bounds: Range) -> bool:
    """Whether `value` is within `bounds`, inclusive; a None bound leaves that side open, but a None `value`
    never matches (there is nothing to compare)."""
    if value is None:
        return False
    low, high = bounds
    return (low is None or value >= low) and (high is None or value <= high)


def _is_double_star_group_member(obj: Object, group_names: frozenset[str]) -> bool:
    """Whether `obj` is a double star pair that belongs to one of `group_names` (and so would be excluded
    by exclude_group_members when that group itself matched)."""
    return (ObjectType.DOUBLE_STAR in obj.types
            and not obj.is_group
            and any(g.casefold() in group_names for g in obj.groups))


def _object_magnitudes(obj: Object, references: References, band: str | None) -> list[float]:
    """Every component's magnitude picked from the Object's MAGNITUDE, as numbers - one for a plain Object, up
    to two for a double star ("primary;secondary" in the record; a component present but empty, or with no
    value of `band`, is left out rather than treated as a match or a failure). The value of `band` (one of
    MAGNITUDE_BANDS) when given; otherwise the same visual > blue > first priority the Browse table's
    Magnitude column uses. Always read through the reference when the Object itself has none (see
    References.resolved). A `magnitude` range needs every one of these in range to match - a double star
    "brighter than 8" with a primary of 7.5 but a secondary of 11 does not qualify, since the secondary alone
    would not be seen at that brightness either.

    :param obj: the Object to read the magnitude(s) of
    :param references: resolves the reference when `obj` itself has none
    :param band: one of MAGNITUDE_BANDS, or None for the default priority
    :returns: the matching magnitude component(s), as numbers
    """
    raw = references.resolved(obj, ObjectAttribute.MAGNITUDE)
    if not raw:
        return []
    values = []
    for component in raw.split(";"):
        parts = [p.strip() for p in component.split(",") if p.strip()]
        if not parts:
            continue
        if band is not None:
            picked = next((p for p in parts if p.startswith(band) and not (band == "b" and p.startswith("bv"))), None)
        else:
            picked = (next((p for p in parts if p.startswith("v")), None)
                     or next((p for p in parts if p.startswith("b") and not p.startswith("bv")), None)
                     or parts[0])
        if picked is not None:
            try:
                values.append(float(picked[1:]))
            except ValueError:
                pass
    return values


def _object_size(obj: Object, axis: str | None) -> float | None:
    """The value of `axis` (SIZE_AXES) from the Object's SIZE, or - without an axis - the smaller of the
    major and minor diameters, so that a `size` range needs every direction of the Object to be at least
    that big, not just its longest axis. An Object with no minor of its own is treated as circular (as good
    as minor == major) for None and "major"; "minor" alone has nothing to check such an Object against and
    never matches it.

    :param obj: the Object to read the size of
    :param axis: one of SIZE_AXES, or None for the smaller of the two
    :returns: the selected dimension, or None when the Object has no SIZE at all
    """
    major = obj.size_major
    if axis == "major":
        return major
    minor = obj.size_minor
    if axis == "minor":
        return minor
    if major is None:
        return None
    return min(major, minor) if minor is not None else major


def _object_separation(obj: Object, references: References) -> float | None:
    """A double star's separation in arcseconds, the same value the Browse table's Size / Separation column
    shows - see References.resolved_separation.

    :param obj: the Object to read the separation of
    :param references: resolves the reference the separation is usually stored on (the WDS)
    :returns: the separation, or None when there is none
    """
    raw = references.resolved_separation(obj)
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _record_number(obj: Object, key: str) -> float | None:
    value = obj.record.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
