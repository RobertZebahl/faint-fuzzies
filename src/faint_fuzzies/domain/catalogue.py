"""Loading one catalogue file: parsing its records into Objects, with every finding found along the way."""
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import ERROR, WARNING, Finding
from faint_fuzzies.domain.formats import has_second_magnitude, value_errors
from faint_fuzzies.domain.model import (
    COORDINATES_FORMAT,
    OBJECT_ATTRIBUTES,
    Object,
    ObjectAttribute,
    ObjectType,
    ObservationAttribute,
    split_names,
)
from faint_fuzzies.domain.names import expand_names
from faint_fuzzies.domain.observation import is_header, parse_observations
from faint_fuzzies.domain.session import Sessions
from faint_fuzzies.storage import load_json_list

KNOWN_ATTRIBUTES = frozenset(OBJECT_ATTRIBUTES)
STRING_ATTRIBUTES = (ObjectAttribute.NAME, ObjectAttribute.GROUP, ObjectAttribute.TYPE, ObjectAttribute.CONSTELLATION)

__all__ = ["ERROR", "WARNING", "Catalogue", "Finding", "assign_sessions", "load_catalogue", "record_numbers"]


@dataclass
class Catalogue:
    """The valid Objects of one catalogue file, the invalid ones apart, and every finding made while loading it.

    A record with an error is Invalid: it is kept in `invalid` (with what could be read of it and its raw record),
    never in `objects`, so nothing that works on Objects ever meets it. Observations with an error are left out of
    their Object, which stays valid and keeps them in `invalid_observations`; with none left it has nothing to
    publish. Records with warnings only are kept.

    :ivar name: the file name
    :ivar records: the number of records in the file
    :ivar objects: the valid Objects
    :ivar findings: every finding made while loading, for valid and invalid records alike
    :ivar invalid: the Objects built from invalid records
    """
    name: str
    records: int
    objects: list[Object]
    findings: list[Finding]
    invalid: list[Object] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Whether any finding is an error."""
        return any(p.severity == ERROR for p in self.findings)

    @property
    def skipped(self) -> int:
        """How many records were left out of `objects` as invalid - not counting a double-star
        attach-record load_catalogue's `skip` left out deliberately, which is in neither `objects` nor
        `invalid` but is not a problem (see importers.owner_double_stars.is_attach_record)."""
        return len(self.invalid)

    @property
    def ignored_observations(self) -> int:
        """How many observations were left out of their (otherwise valid) Object as invalid."""
        return sum(len(obj.invalid_observations) for obj in self.objects)

    @cached_property
    def group_names(self) -> frozenset[str]:
        """Lower-cased names of the group records of this catalogue."""
        return frozenset(g.casefold() for obj in self.objects if obj.is_group for g in obj.groups)


def load_catalogue(path: Path, sessions: Sessions | None = None, check_values: bool = True,
                   skip: Callable[[Any], bool] | None = None) -> Catalogue:
    """Loads a catalogue file. With sessions, private observations are assigned to their session. `check_values`
    has the formats of the values (see formats.py) checked; a record with a value of the wrong format is an error
    and left out. The catalogues of others come from the converters and are checked by `validate`, not on every
    load, which they would make slower by some 5 %.

    :param path: the catalogue file to load
    :param sessions: the sessions to assign private observations to
    :param check_values: whether to check the formats of the values
    :param skip: when given, a record it returns True for is left out entirely - neither parsed nor
        counted as invalid (the own catalogue's double-star attach-records; see
        importers.owner_double_stars.is_attach_record)
    :returns: the loaded catalogue
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    data = load_json_list(path, "records")

    objects: list[Object] = []
    invalid: list[Object] = []
    findings: list[Finding] = []
    for index, record in enumerate(data, start=1):
        if skip is not None and skip(record):
            continue
        obj, record_findings = _parse_record(path.name, index, record, sessions, check_values)
        findings.extend(record_findings)
        (objects if obj.valid else invalid).append(obj)
    return Catalogue(name=path.name, records=len(data), objects=objects, findings=findings, invalid=invalid)


def _parse_record(source: str, index: int, record: Any, sessions: Sessions | None,
                  check_values: bool = True) -> tuple[Object, list[Finding]]:
    """The Object of a record and the findings made about it. An Object with an error is not `valid`: it holds
    what could be read of the record (the names, types and so on that are usable) and the record itself.

    :param source: the catalogue file name
    :param index: the record's 1-based position in the file
    :param record: the raw record
    :param sessions: the sessions to assign private observations to
    :param check_values: whether to check the formats of the values
    :returns: the Object and the findings made about its record
    """
    if not isinstance(record, dict):
        return (Object({}, (), (), (), "", (), index, source, valid=False, raw=record),
                [Finding(source, index, None, None, ERROR, "record is not a JSON object")])

    values = {key: record.get(key, "") for key in STRING_ATTRIBUTES}
    names = split_names(values[ObjectAttribute.NAME]) if isinstance(values[ObjectAttribute.NAME], str) else ()
    groups = split_names(values[ObjectAttribute.GROUP]) if isinstance(values[ObjectAttribute.GROUP], str) else ()
    label = (names or groups or (None,))[0]
    constellation = (values[ObjectAttribute.CONSTELLATION].strip()
                     if isinstance(values[ObjectAttribute.CONSTELLATION], str) else "")

    findings: list[Finding] = []

    def report(_attribute: str, _message: str, severity: str = ERROR) -> None:
        findings.append(Finding(source, index, label, _attribute, severity, _message))

    def invalid(_types: list[ObjectType], _observations=(), invalid_observations=()) -> tuple[Object, list[Finding]]:
        return (Object(record, expand_names(names), expand_names(groups), tuple(_types), constellation,
                       tuple(_observations), index, source, valid=False,
                       invalid_observations=tuple(invalid_observations)),
                findings)

    for key in STRING_ATTRIBUTES:
        if not isinstance(values[key], str):
            report(key, f"{key} must be a string")
    if (not names and not groups and isinstance(values[ObjectAttribute.NAME], str)
            and isinstance(values[ObjectAttribute.GROUP], str)):
        report(ObjectAttribute.NAME, "record has neither NAME nor GROUP")

    types: list[ObjectType] = []
    if isinstance(values[ObjectAttribute.TYPE], str):
        for code in (c.strip() for c in values[ObjectAttribute.TYPE].split(",")):
            if not code:
                continue
            try:
                types.append(ObjectType.parse(code))
            except ValueError as exc:
                report(ObjectAttribute.TYPE, str(exc))

    coordinates = record.get(ObjectAttribute.COORDINATES, "")
    if not isinstance(coordinates, str):
        report(ObjectAttribute.COORDINATES, "COORDINATES must be a string")
    elif coordinates and not COORDINATES_FORMAT.fullmatch(coordinates):
        report(ObjectAttribute.COORDINATES, f"invalid coordinates '{coordinates}': expected hhmmss.ss,\u00b1ddmmss.ss")

    if check_values:
        for attribute, message in value_errors(record):
            report(attribute, message)

    raw_observations = record.get(ObjectAttribute.OBSERVATIONS, [])
    if not isinstance(raw_observations, list):
        report(ObjectAttribute.OBSERVATIONS, "OBSERVATIONS must be a list")

    for key in sorted(record.keys() - KNOWN_ATTRIBUTES):
        report(key, "unknown attribute", WARNING)

    if any(p.severity == ERROR for p in findings):
        return invalid(types)

    def report_observation(_number: int, _attribute: str | None, _message: str, severity: str) -> None:
        findings.append(Finding(source, index, label, _attribute, severity, _message, _number))

    left_out: list[tuple[int, Any]] = []
    if raw_observations:
        observations = parse_observations(raw_observations, report_observation, ObjectType.DOUBLE_STAR in types)
        kept = {id(o.record) for o in observations}
        left_out = [(n, raw) for n, raw in enumerate(raw_observations, start=1) if id(raw) not in kept]
        if not _check_headers(observations, raw_observations, report):
            return invalid(types, observations, left_out)
        if sessions is not None:
            assign_sessions(observations, sessions, raw_observations, report_observation)
        if check_values:
            _check_order(observations, raw_observations, report_observation)
    else:  # most records, those of the catalogues of others: nothing to parse, check or assign
        observations = ()
    if (check_values and ObjectType.DOUBLE_STAR not in types
            and has_second_magnitude(str(record.get(ObjectAttribute.MAGNITUDE, "")))):
        report(ObjectAttribute.MAGNITUDE, "a second magnitude is only for a double star", WARNING)

    return (Object(record, expand_names(names), expand_names(groups), tuple(types), constellation, observations,
                   index, source, invalid_observations=tuple(left_out)),
            findings)


def record_numbers(raw_observations: list) -> dict[int, int]:
    """Maps id(observation.record) to its 1-based position among the raw observations, surviving that
    some may have been dropped for having an error.

    :param raw_observations: the raw OBSERVATIONS list of a record
    :returns: id(raw observation) -> its 1-based position
    """
    return {id(raw): n for n, raw in enumerate(raw_observations, start=1)}


def _check_order(observations, raw_observations: list, report) -> None:
    """Reports a warning at the first private observation that is earlier than the one before it: they are
    kept in the order of their date and time.

    :param observations: the parsed observations
    :param raw_observations: the raw OBSERVATIONS list, to number the warning against
    :param report: called with (number, attribute, message, severity) to report a finding
    """
    numbers = record_numbers(raw_observations)
    previous = None
    for observation in observations:
        if observation.public or observation.start is None:
            continue
        if previous is not None and observation.start < previous:
            report(numbers[id(observation.record)], ObservationAttribute.DATE,
                  "the observations are not in the order of their date and time", WARNING)
            return
        previous = observation.start


def _check_headers(observations, raw_observations: list, report) -> bool:
    """An Object has at most one Header (a public observation with no instrument).

    :param observations: the parsed observations
    :param raw_observations: the raw OBSERVATIONS list, to number the finding against
    :param report: called with (attribute, message) to report a finding
    :returns: whether the Object has at most one Header
    """
    numbers = record_numbers(raw_observations)
    found = sorted(numbers[id(o.record)] for o in observations if is_header(o))
    if len(found) > 1:
        report(ObjectAttribute.OBSERVATIONS, "more than one header (a public observation with no instrument): "
                                             f"observations {', '.join(str(n) for n in found)}")
        return False
    return True


def assign_sessions(observations, sessions: Sessions, raw_observations: list, report) -> None:
    """Assigns each private observation to the session containing it, warning when none or several do (the
    earliest of several is used). Public, since a double-star attach-record's observations (see
    importers.owner_double_stars) need the identical assignment outside this module's own per-record loop.

    :param observations: the parsed observations
    :param sessions: the sessions to assign observations to
    :param raw_observations: the raw OBSERVATIONS list, to number the warning against
    :param report: called with (number, attribute, message, severity) to report a finding
    """
    numbers = record_numbers(raw_observations)
    for observation in observations:
        if observation.public:
            continue
        number = numbers[id(observation.record)]
        found = sessions.containing(observation.start, observation.end)
        if not found:
            report(number, ObservationAttribute.DATE, "no session contains this observation", WARNING)
            continue
        observation.session = found[0]
        if len(found) > 1:
            report(number, ObservationAttribute.DATE, "several sessions contain this observation; the earliest is used",
                  WARNING)
