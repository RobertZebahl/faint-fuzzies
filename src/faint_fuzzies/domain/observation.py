"""An Observation of an Object: the instrument, visibility, date/time and texts. Parsing a record's
OBSERVATIONS into Observations, and the small related parsers (optic, visibility)."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from faint_fuzzies.domain.conditions import ConditionAttribute, condition_finding
from faint_fuzzies.domain.findings import ERROR, WARNING
from faint_fuzzies.domain.model import OBSERVATION_ATTRIBUTES, Object, ObservationAttribute
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.domain.session import Session
from faint_fuzzies.domain.timespan import parse_date_time

# report(observation number, attribute, message, severity)
Report = Callable[[int, str | None, str, str], None]

TELESCOPE_DESIGNS = frozenset({"R", "N", "M", "SC"})
_NUMBER = r"[0-9]+"
_GRADE = re.compile(r"([1-6])(?:-([1-6]))?")
# Grades from this number on mean "not seen": 6 for any other Object, 3 for a double star - each
# scale's last grade is its only failed one, with nothing finer beyond it.
FAILED_FROM_DEEP_SKY = 6
FAILED_FROM_DOUBLE_STAR = 3
_MAX_GRADE = {True: FAILED_FROM_DOUBLE_STAR, False: FAILED_FROM_DEEP_SKY}
# a range never reaches as far as the failed grades, since those are simply failed, with nothing finer
# to be uncertain about
_LAST_SEEN_GRADE = {True: FAILED_FROM_DOUBLE_STAR - 1, False: FAILED_FROM_DEEP_SKY - 1}


class OpticType(Enum):
    NAKED_EYE = "naked_eye"
    BINOCULARS = "binoculars"
    TELESCOPE = "telescope"


class Method(Enum):
    VISUAL = "visual"
    PHOTOGRAPHIC = "photographic"


class Difficulty(Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    FAILED = "FAILED"


class Color(Enum):
    RED = "RED"
    ORANGE = "ORANGE"


@dataclass(frozen=True)
class Optic:
    """The instrument, written as "A", "B,10x50", "S,56" or "R,70,400" (design, aperture, focal length).

    :ivar code: the instrument as written
    :ivar type: naked eye, binoculars or telescope
    :ivar design: the telescope design code, None for the naked eye or binoculars
    :ivar aperture: in millimeters, None for the naked eye
    :ivar magnification: binoculars only
    :ivar focal_length: telescopes only, in millimeters
    """
    code: str
    type: OpticType
    design: str | None = None
    aperture: int | None = None
    magnification: int | None = None
    focal_length: int | None = None


@dataclass(frozen=True)
class Grade:
    """A private observation's numeric result; a range such as "3-4" is an uncertain reading.

    :ivar low: the lower (better) end of the grade
    :ivar high: the higher (worse) end; equal to `low` when the grade is not a range
    """
    low: int
    high: int


Result = Grade | Difficulty | Color


@dataclass(frozen=True)
class VisibilityEntry:
    """One telescope magnification's visibility: a Result (or None for no reading) and an optional filter.

    :ivar magnification: the magnification used; None for the naked eye or binoculars
    :ivar result: the result, or None when it reports a filter alone
    :ivar filter: the filter used, if any
    """
    magnification: int | None
    result: Result | None
    filter: str | None


# the import formats of the project files; the Global format also feeds the projects, but is no project file
PROJECT_FORMATS = frozenset({
    "project-double-stars-visual", "project-double-stars-photographic", "project-deep-sky-with-binoculars"
})


@dataclass(eq=False)
class Observation:
    """One observation of an Object, private (the user's own) or community (another observer's, imported
    from a project file). `observer`, `rating`, `notes`, `source` and `format` are only ever carried by
    the observations of other observers.

    :ivar record: the raw record
    :ivar public: whether this is a Header (see is_header), never a private observation proper
    :ivar optic: the instrument used, None for a Header
    :ivar visibility: the visibility entries, empty for a Header
    :ivar start: when the observation started, None for a community observation (dated by its Session)
    :ivar end: when the observation ended
    :ivar session: the session it belongs to, if any
    :ivar observer: who made it; None means the user
    :ivar method: "visual" or "photographic"
    :ivar rating: 0 to 3 stars; 0 is none
    :ivar notes: private remarks of the observer, never published
    :ivar source: the file and line it was read from
    :ivar format: the import format it came from; None for the user's own observations
    """
    record: dict[str, Any]
    public: bool
    optic: Optic | None
    visibility: tuple[VisibilityEntry, ...]
    start: datetime | None = None
    end: datetime | None = None
    session: Session | None = None
    observer: Observer | None = None
    method: str = "visual"
    rating: int = 0
    notes: str = ""
    source: str = ""
    format: str | None = None

    @property
    def project_only(self) -> bool:
        """Read from a project file (whoever made it). Such an observation gives a bare aperture or a plain
        binocular size and is shown as given: optic_names.json is not applied to it."""
        return self.format in PROJECT_FORMATS

    @property
    def descriptions(self) -> tuple[tuple[str | None, str], ...]:
        """The texts of the observation as (language, text) pairs, language "DE", "EN" or None for a text that
        belongs to no language in particular: a plain DESCRIPTION, or a German and an English text that are
        the same (another observer's single text is stored under both). Both languages are given when both are there."""
        text = self.record.get
        german = str(text(ObservationAttribute.DESCRIPTION_DE) or "").strip()
        english = str(text(ObservationAttribute.DESCRIPTION_EN) or "").strip()
        found: list[tuple[str | None, str]] = []
        if plain := str(text(ObservationAttribute.DESCRIPTION) or "").strip():
            found.append((None, plain))
        if german and german == english:
            found.append((None, german))
        else:
            found += [(language, value) for language, value in (("DE", german), ("EN", english)) if value]
        return tuple(found)

    @property
    def sketches(self) -> tuple[str, ...]:
        return _file_names(self.record, ObservationAttribute.SKETCH)

    @property
    def photographs(self) -> tuple[str, ...]:
        return _file_names(self.record, ObservationAttribute.PHOTOGRAPH)

    @property
    def images(self) -> tuple[str, ...]:
        return _file_names(self.record, ObservationAttribute.IMAGE)

    @property
    def has_sketch(self) -> bool:
        return bool(self.sketches)

    @property
    def has_photograph(self) -> bool:
        return bool(self.photographs)

    @property
    def has_image(self) -> bool:
        return bool(self.images)


@dataclass(frozen=True)
class FoundObservation:
    """An observation and the Object that holds it.

    :ivar observation: the observation
    :ivar object: the object it belongs to
    """
    observation: Observation
    object: Object


def is_header(observation: Observation) -> bool:
    """A Header: a public Own observation (never an imported one) with no instrument and no photograph or
    sketch - a photograph or sketch means it reports what was seen, whether or not the optic is known.

    :param observation: the observation to check
    :returns: whether it is a Header
    """
    return (observation.public and observation.format is None and observation.optic is None
            and not observation.has_photograph and not observation.has_sketch)


def _file_names(record: dict[str, Any], key: str) -> tuple[str, ...]:
    return tuple(name for name in str(record.get(key, "")).split(",") if name)


def parse_optic(code: str) -> Optic:
    """Parses an OPTIC value: "A" (naked eye), "B,<magnification>x<aperture>" (binoculars), "S,<aperture>"
    or "<design>,<aperture>,<focal length>" (telescope).

    :param code: the OPTIC value to parse
    :returns: the parsed optic
    :raises ValueError: when `code` is none of these forms
    """
    if code == "A":
        return Optic(code, OpticType.NAKED_EYE)
    parts = code.split(",")
    if len(parts) == 2 and parts[0] == "B":
        match = re.fullmatch(rf"({_NUMBER})x({_NUMBER})", parts[1])
        if match:
            return Optic(code, OpticType.BINOCULARS, "B", aperture=int(match[2]), magnification=int(match[1]))
    elif len(parts) == 2 and parts[0] == "S" and re.fullmatch(_NUMBER, parts[1]):
        return Optic(code, OpticType.TELESCOPE, "S", aperture=int(parts[1]))
    elif (len(parts) == 3 and re.fullmatch("[A-Za-z]+", parts[0])
          and re.fullmatch(_NUMBER, parts[1]) and re.fullmatch(_NUMBER, parts[2])):
        return Optic(code, OpticType.TELESCOPE, parts[0], aperture=int(parts[1]), focal_length=int(parts[2]))
    raise ValueError(f"invalid optic '{code}'")


def parse_visibility(text: str, optic: Optic, double_star: bool) -> tuple[VisibilityEntry, ...]:
    """Entries are separated by ";". A telescope entry is "magnification,result,filter", any part
    may be empty; for binoculars and the naked eye the magnification is fixed, so "result,filter".

    :param text: the VISIBILITY value to parse
    :param optic: the instrument used, to know the entry shape
    :param double_star: whether the object observed is a double star, which grades on a narrower scale
    :returns: the parsed entries
    :raises ValueError: when an entry has too many fields, or an invalid magnification or result
    """
    telescope = optic.type is OpticType.TELESCOPE
    entries = []
    for entry in text.split(";"):
        fields = [f.strip() for f in entry.split(",")]
        if len(fields) > (3 if telescope else 2):
            raise ValueError(f"too many fields in visibility entry '{entry.strip()}'")
        if telescope:
            fields = fields + [""] * (3 - len(fields))
            magnification, result, filter_ = fields
        else:
            fields = fields + [""] * (2 - len(fields))
            magnification, (result, filter_) = "", fields
        if magnification and not re.fullmatch(_NUMBER, magnification):
            raise ValueError(f"invalid magnification '{magnification}' in visibility entry '{entry.strip()}'")
        entries.append(VisibilityEntry(int(magnification) if magnification else None,
                                       _parse_result(result, double_star), filter_ or None))
    return tuple(entries)


def _check_visibility_results(visibility: tuple[VisibilityEntry, ...], public: bool,
                              error: Callable[[str, str], None]) -> None:
    """Flags a Grade result on a public observation, or a Difficulty/Color result on a private one: Grade
    is private observations only, Difficulty and Color are public observations only.

    :param visibility: the observation's parsed visibility entries
    :param public: whether the observation is public
    :param error: called with (attribute, message) to report a finding
    """
    for entry in visibility:
        if public and isinstance(entry.result, Grade):
            error(ObservationAttribute.VISIBILITY, "a public observation cannot have a numeric Grade result "
                                                   "(Grade is private observations only)")
        elif not public and isinstance(entry.result, (Difficulty, Color)):
            error(ObservationAttribute.VISIBILITY, "a private observation cannot have a Difficulty or Color "
                                                   "result (those are public observations only)")


def _parse_result(token: str, double_star: bool) -> Result | None:
    """Parses one visibility entry's result token: empty for None, a Difficulty or Color name, or a Grade.

    A Grade is a bare digit 1-6 (1-3 for a double star), or a range of two adjacent grades that never
    reaches past the last "seen" one (`1-2`/`2-3`/`3-4`/`4-5`, or `1-2` alone for a double star) - never
    reversed, since that is more likely a typo than a deliberately backwards range.

    :param token: the result token to parse
    :param double_star: whether the object observed is a double star, which grades on a narrower scale
    :returns: the parsed result, or None when the token is empty
    :raises ValueError: when the token is none of these, or a Grade does not fit its scale's shape
    """
    if not token:
        return None
    for enum in (Difficulty, Color):
        if token.upper() in enum.__members__:
            return enum[token.upper()]
    match = _GRADE.fullmatch(token)
    if not match:
        raise ValueError(f"invalid visibility result '{token}'")
    low, high = int(match[1]), int(match[2]) if match[2] else None
    max_grade, last_seen = _MAX_GRADE[double_star], _LAST_SEEN_GRADE[double_star]
    kind = "a double star" if double_star else "this scale"
    if low > max_grade or (high is not None and high > max_grade):
        raise ValueError(f"invalid visibility result '{token}' for {kind}")
    if high is not None:
        if high < low:
            raise ValueError(f"visibility result '{token}' is a reversed range")
        if high != low + 1 or high > last_seen:
            raise ValueError(f"visibility result '{token}' is not a range of two adjacent grades for {kind}")
    return Grade(low, high if high is not None else low)


def parse_observations(records: list[Any], report: Report, double_star: bool) -> tuple[Observation, ...]:
    """Observations with an error are reported and left out; the others are returned.

    :param records: the raw OBSERVATIONS list to parse
    :param report: called with (observation number, attribute, message, severity) to report a finding
    :param double_star: whether the object observed is a double star, which grades on a narrower scale
    :returns: the valid observations, in order
    """
    observations = []
    for number, record in enumerate(records, start=1):
        observation = _parse_observation(number, record, report, double_star)
        if observation is not None:
            observations.append(observation)
    return tuple(observations)


def _parse_observation(number: int, record: Any, report: Report, double_star: bool) -> Observation | None:
    """The Observation of a record, or None when it has an error.

    :param number: the record's 1-based position among the raw observations
    :param record: the raw record
    :param report: called with (observation number, attribute, message, severity) to report a finding
    :param double_star: whether the object observed is a double star, which grades on a narrower scale
    :returns: the parsed observation, or None when the record has an error
    """
    if not isinstance(record, dict):
        report(number, None, "observation is not a JSON object", ERROR)
        return None

    failed = False

    def error(attribute: str, _message: str) -> None:
        nonlocal failed
        failed = True
        report(number, attribute, _message, ERROR)

    for key in sorted(record.keys() - set(OBSERVATION_ATTRIBUTES)):
        report(number, key, "unknown attribute", WARNING)
    for key in OBSERVATION_ATTRIBUTES:
        if key in record and not isinstance(record[key], str):
            error(key, f"{key} must be a string")
    if failed:
        return None

    # Spaces outside the descriptions carry no meaning; the writer removes them, so the parser ignores them.
    text = {k: record[k] if k.startswith(ObservationAttribute.DESCRIPTION) else record[k].replace(" ", "")
            for k in OBSERVATION_ATTRIBUTES if k in record}

    date, time = text.get(ObservationAttribute.DATE, ""), text.get(ObservationAttribute.TIME, "")
    start = end = None
    if bool(date) != bool(time):
        error(ObservationAttribute.TIME if date else ObservationAttribute.DATE, "DATE and TIME must be given together")
    elif date:
        try:
            start, end = parse_date_time(date, time)
        except ValueError as exc:
            error(ObservationAttribute.DATE, str(exc))

    optic = None
    if text.get(ObservationAttribute.OPTIC):
        try:
            optic = parse_optic(text[ObservationAttribute.OPTIC])
        except ValueError as exc:
            error(ObservationAttribute.OPTIC, str(exc))
        else:
            if optic.design not in (None, "B", "S") and optic.design not in TELESCOPE_DESIGNS:
                report(number, ObservationAttribute.OPTIC, f"unknown telescope design '{optic.design}'", WARNING)

    public = start is None
    visibility: tuple[VisibilityEntry, ...] = ()
    if text.get(ObservationAttribute.VISIBILITY):
        if optic is not None:
            try:
                visibility = parse_visibility(text[ObservationAttribute.VISIBILITY], optic, double_star)
            except ValueError as exc:
                error(ObservationAttribute.VISIBILITY, str(exc))
            else:
                _check_visibility_results(visibility, public, error)
        elif not text.get(ObservationAttribute.OPTIC):
            report(number, ObservationAttribute.VISIBILITY,
                  "visibility is ignored because there is no OPTIC", WARNING)

    has_photograph = bool(text.get(ObservationAttribute.PHOTOGRAPH))
    has_sketch = bool(text.get(ObservationAttribute.SKETCH))
    if has_sketch and optic is None:
        error(ObservationAttribute.SKETCH, "SKETCH requires OPTIC to be stated")

    for key, value in text.items():
        if key not in ConditionAttribute:
            continue
        message = condition_finding(ConditionAttribute(key), value)
        if message:
            report(number, key, message, WARNING)

    if failed:
        return None
    # own observations have no METHOD attribute; inferred from which medium is attached - a photograph with
    # no sketch is photographic, everything else (a sketch, or neither) is visual, matching the Double Stars
    # observer's own per-file visual.csv/photographic.csv split
    method = "photographic" if has_photograph and not has_sketch else "visual"
    return Observation(record, public=public, optic=optic, visibility=visibility, start=start, end=end,
                       method=method)
