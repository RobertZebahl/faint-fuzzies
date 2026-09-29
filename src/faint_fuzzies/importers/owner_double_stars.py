"""Reads the own catalogue's double-star attach-records: a double star record (TYPE `**`) in
objects.json that is not marked DISABLE_WDS is not kept as an independent Object there - it is matched
to its WDS pair or group by NAME and COMPONENT, the same way a Community observation is (see attach.py),
and its observations and tags attach to the match instead. Nothing is written back.

A DISABLE_WDS record is unaffected: it stays a full, independent Object, exactly as every other
catalogue's record does, loaded through the usual domain.catalogue path.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.catalogue import assign_sessions
from faint_fuzzies.domain.findings import ERROR, Finding
from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.domain.observation import Observation, parse_observations
from faint_fuzzies.domain.session import Sessions
from faint_fuzzies.storage import load_json_list

# the attributes an attach-record may carry besides NAME/COMPONENT/OBSERVATIONS - everything an Object
# attribute could mean (CONSTELLATION, COORDINATES, GROUP, MAGNITUDE, TYPE beyond "**") has nothing to
# attach to, since the record is not an independent Object
TAG_ATTRIBUTES = (ObjectAttribute.RATING, ObjectAttribute.PROJECT_DOUBLE_STARS_LISTS, ObjectAttribute.NOTES,
                  ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS, ObjectAttribute.PUBLISH_WITHOUT_OBSERVATION)


def is_attach_record(record: Any) -> bool:
    """Whether a raw own-catalogue record is a double-star attach-record.

    :param record: the raw record
    :returns: whether it is a double star (TYPE `**`) not marked DISABLE_WDS
    """
    return (isinstance(record, dict) and record.get(ObjectAttribute.TYPE) == "**"
            and not record.get(ObjectAttribute.DISABLE_WDS))


@dataclass(frozen=True)
class OwnerDoubleStar:
    """One own-catalogue double-star attach-record, understood.

    :ivar number: its 1-based position in objects.json, for findings
    :ivar name: its own NAME value, unparsed - matched the same way a Community row's name is
    :ivar component: its own COMPONENT value, unparsed: blank, exact text, or "*"
    :ivar tags: the attribute -> raw value of whichever of TAG_ATTRIBUTES it carries
    :ivar observations: its own OBSERVATIONS, parsed
    """
    number: int
    name: str
    component: str
    tags: dict[str, Any] = field(default_factory=dict)
    observations: tuple[Observation, ...] = ()


def read_owner_double_stars(path: Path, findings: list[Finding],
                            sessions: Sessions | None = None) -> list[OwnerDoubleStar]:
    """Reads every double-star attach-record of the own catalogue.

    :param path: the own catalogue file
    :param findings: the list a record's findings are appended to
    :param sessions: the sessions to assign private observations to, the same as domain.catalogue's own
        per-record loop does - without this, a private observation here would never match any session
        (the Browse page's session filter, its session list's object counts, and the Statistics page's
        per-location counts all read Observation.session)
    :returns: the understood records, in file order; a record with no usable NAME is reported and left out
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    source = path.name
    result = []
    for number, record in enumerate(load_json_list(path, "records"), start=1):
        if not is_attach_record(record):
            continue
        name = record.get(ObjectAttribute.NAME, "")
        if not isinstance(name, str) or not name.strip():
            findings.append(Finding(source, number, None, ObjectAttribute.NAME, ERROR,
                                    "double star attach-record has no NAME"))
            continue
        component = str(record.get(ObjectAttribute.COMPONENT, "") or "").strip()
        tags = {attribute: record[attribute] for attribute in TAG_ATTRIBUTES if attribute in record}

        report: Callable[[int, str | None, str, str], None] = _reporter(findings, source, number, name)
        raw_observations = record.get(ObjectAttribute.OBSERVATIONS, [])
        observations = (parse_observations(raw_observations, report, True)
                        if isinstance(raw_observations, list) else ())
        if sessions is not None and observations:
            assign_sessions(observations, sessions, raw_observations, report)
        result.append(OwnerDoubleStar(number, name, component, tags, observations))
    return result


def _reporter(findings: list[Finding], source: str, number: int,
             name: str) -> Callable[[int, str | None, str, str], None]:
    def report(obs_number: int, attribute: str | None, message: str, severity: str) -> None:
        findings.append(Finding(source, number, name, attribute, severity, message, obs_number))
    return report
