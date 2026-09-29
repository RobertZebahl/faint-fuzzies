"""Findings about the data, found while loading or validating a data directory: issues with a record, attached
to the Object or Observation it concerns (see faint_fuzzies.checks)."""
from dataclasses import asdict, dataclass
from typing import Any

ERROR = "error"
WARNING = "warning"
INFO = "info"


class CatalogueError(Exception):
    """A data file itself cannot be used (missing, unreadable, not a JSON list)."""


@dataclass(frozen=True)
class Finding:
    """One finding about a record, at `severity` ERROR, WARNING or INFO.

    :ivar catalogue: the file the record is from
    :ivar record: the record's line or position in the file
    :ivar object: the label of the Object the finding concerns, if any
    :ivar attribute: the attribute of the record the finding concerns, if any
    :ivar severity: ERROR, WARNING or INFO
    :ivar message: the human-readable description of the finding
    :ivar observation: the index of the Observation the finding concerns, if any
    """
    catalogue: str
    record: int
    object: str | None
    attribute: str | None
    severity: str
    message: str
    observation: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
