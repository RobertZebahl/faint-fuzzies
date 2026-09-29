"""Loading the sessions file: periods of observing at one place, that private observations are assigned
to by date and time (see catalogue.py)."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.conditions import ConditionAttribute, condition_finding
from faint_fuzzies.domain.findings import ERROR, WARNING, Finding
from faint_fuzzies.domain.timespan import parse_date_time
from faint_fuzzies.storage import load_json_list


class SessionAttribute(StrEnum):
    """Attributes of a session record, in the order they are written."""
    DATE = "DATE"
    TIME = "TIME"
    LOCATION = "LOCATION"
    BORTLE = "BORTLE"
    NELM = "NELM"
    SQM = "SQM"
    SQML = "SQML"
    SEEING = "SEEING"
    EQUIPMENT = "EQUIPMENT"
    DESCRIPTION = "DESCRIPTION"


SESSION_ORDER = tuple(SessionAttribute)
SESSION_ATTRIBUTES = frozenset(SESSION_ORDER)
CONDITION_ATTRIBUTES = (ConditionAttribute.BORTLE, ConditionAttribute.NELM, ConditionAttribute.SQM,
                        ConditionAttribute.SQML, ConditionAttribute.SEEING)


@dataclass(frozen=True)
class Location:
    """Where a session took place.

    :ivar name: the location's name
    :ivar latitude: in degrees
    :ivar longitude: in degrees
    :ivar height: in meters
    :ivar utc_offset: given, but never read anywhere - no timezone is applied at all, since there is
        none in the source data to begin with; session times are kept as naive local clock time
        (see timespan.parse_date_time)
    """
    name: str
    latitude: float
    longitude: float
    height: int
    utc_offset: int


@dataclass(eq=False)
class Session:
    """A period of observing at one place. Private observations belong to it by date and time.

    :ivar record: the raw record
    :ivar start: when the session started
    :ivar end: when the session ended
    :ivar location: where the session took place
    :ivar conditions: the observing conditions given, by ConditionAttribute
    :ivar number: its place in the sessions file, from 1
    """
    record: dict[str, Any]
    start: datetime
    end: datetime
    location: Location
    conditions: dict[ConditionAttribute, str]
    number: int = 0


class Sessions:
    """The sessions of one sessions file, in start order, with every finding made while loading it."""

    def __init__(self, name: str, records: int, sessions: list[Session], findings: list[Finding]):
        """:param name: the file name
        :param records: the number of records in the file
        :param sessions: the valid sessions
        :param findings: the findings made while loading, before the overlap check this adds its own to
        """
        self.name = name
        self.records = records
        self.sessions = sorted(sessions, key=lambda s: s.start)
        self.findings = findings + _overlap_findings(name, self.sessions)
        self._by_date: dict[date, list[Session]] = defaultdict(list)
        for session in self.sessions:
            day = session.start.date()
            while day <= session.end.date():
                self._by_date[day].append(session)
                day += timedelta(days=1)

    def containing(self, start: datetime, end: datetime) -> list[Session]:
        """The sessions that contain the whole period, earliest first.

        :param start: the period's start
        :param end: the period's end
        :returns: the sessions that contain it
        """
        return [s for s in self._by_date.get(start.date(), ()) if s.start <= start and end <= s.end]


def _overlap_findings(source: str, sessions: list[Session]) -> list[Finding]:
    """An error for each session that overlaps an earlier one (sessions sorted by start), at the later one's
    record: an observer is at one place at a time, and an observation inside both would have no single session.
    Sessions that only touch (one ends when the next starts) do not overlap.

    :param source: the sessions file name
    :param sessions: the sessions to check, sorted by start
    :returns: the overlap findings made, sorted by record
    """
    findings: list[Finding] = []
    running: list[Session] = []
    for session in sessions:
        running = [other for other in running if other.end > session.start]
        findings.extend(Finding(source, session.number, None, SessionAttribute.DATE, ERROR,
                                f"overlaps the session of record {other.number} "
                                f"({_period(other)}, {other.location.name})")
                        for other in running)
        running.append(session)
    return sorted(findings, key=lambda p: p.record)


def _period(session: Session) -> str:
    return f"{session.start:%Y-%m-%d %H:%M} - {session.end:%Y-%m-%d %H:%M}"


def load_sessions(path: Path) -> Sessions:
    """Loads a sessions file.

    :param path: the sessions file to load
    :returns: the loaded sessions
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    data = read_session_records(path)
    sessions: list[Session] = []
    findings: list[Finding] = []
    for index, record in enumerate(data, start=1):
        session, record_findings = _parse_session(path.name, index, record)
        findings.extend(record_findings)
        if session is not None:
            sessions.append(session)
    return Sessions(path.name, len(data), sessions, findings)


def read_session_records(path: Path) -> list[Any]:
    """The records of a sessions file as they are written, valid or not.

    :param path: the sessions file to read
    :returns: the raw records
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    return load_json_list(path, "sessions")


def _parse_session(source: str, index: int, record: Any) -> tuple[Session | None, list[Finding]]:
    """The Session of a record and the findings made about it; None when the record has an error (no Session
    without a valid date/time span and a valid location is ever returned).

    :param source: the sessions file name
    :param index: the record's 1-based position in the file
    :param record: the raw record
    :returns: the session (or None) and the findings made about its record
    """
    if not isinstance(record, dict):
        return None, [Finding(source, index, None, None, ERROR, "session is not a JSON object")]

    findings: list[Finding] = []

    def report(attribute: str, _message: str, severity: str = ERROR) -> None:
        findings.append(Finding(source, index, None, attribute, severity, _message))

    for key in sorted(record.keys() - SESSION_ATTRIBUTES):
        report(key, "unknown attribute", WARNING)
    for key, value in record.items():
        if key in SESSION_ATTRIBUTES and not isinstance(value, str):
            report(key, f"{key} must be a string")
    if any(p.severity == ERROR for p in findings):
        return None, findings

    span = None
    if not record.get(SessionAttribute.DATE) or not record.get(SessionAttribute.TIME):
        report(SessionAttribute.DATE, "a session needs DATE and TIME")
    else:
        try:
            span = parse_date_time(record[SessionAttribute.DATE], record[SessionAttribute.TIME])
        except ValueError as exc:
            report(SessionAttribute.DATE, str(exc))

    location = None
    try:
        name, latitude, longitude, height, utc_offset = (
            e.strip() for e in record.get(SessionAttribute.LOCATION, "").split(";"))
        location = Location(name, float(latitude), float(longitude), int(height), int(utc_offset))
    except ValueError:
        report(SessionAttribute.LOCATION, "LOCATION must be 'name;latitude;longitude;height;utc offset'")

    conditions = {k: record[k] for k in CONDITION_ATTRIBUTES if record.get(k)}
    for key, value in conditions.items():
        message = condition_finding(key, value)
        if message:
            report(key, message, WARNING)

    if span is None or location is None:
        return None, findings
    return Session(record, span[0], span[1], location, conditions, index), findings
