"""Validates observing-condition values (Bortle class, NELM, SQM, SQM-L, seeing) typed by hand against the
loose formats they are usually given in."""
import re
from enum import StrEnum

_NELM = r"\d+(?:\.\d+)?\+?"
_SQM = r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?"
_SEEING = r"\d(?:-\d)?/\d"


class ConditionAttribute(StrEnum):
    """A Condition (see CONTEXT.md): the sky readings of a Session or a Public observation, and the Local
    conditions near the object ("_LOCAL") an Observation may add of its own. The same field names
    ObservationAttribute and SessionAttribute carry among their own, wider set of attributes."""
    BORTLE = "BORTLE"
    NELM = "NELM"
    NELM_LOCAL = "NELM_LOCAL"
    SQM = "SQM"
    SQML = "SQML"
    SQML_LOCAL = "SQML_LOCAL"
    SEEING = "SEEING"
    SEEING_LOCAL = "SEEING_LOCAL"


# Observing conditions as typed by hand: Bortle class, naked-eye limiting magnitude, sky quality meter
# reading (without and with a lens restricting the field of view) and seeing. NELM and SQM/SQM-L accept
# any positive number, with or without a decimal part, never negative - a real value never needs more
# than that. A trailing "-"/"+" marks a tendency on Bortle, on either side of a range independently
# ("6--7" is "6-" to "7"); a trailing "+" means "at least" on NELM - SQM, SQM-L and seeing are never
# signed.
CONDITION_PATTERNS = {
    ConditionAttribute.BORTLE: re.compile(r"[1-9][+-]?(?:-[1-9][+-]?)?"),
    ConditionAttribute.NELM: re.compile(_NELM),
    ConditionAttribute.NELM_LOCAL: re.compile(_NELM),
    ConditionAttribute.SQM: re.compile(_SQM),
    ConditionAttribute.SQML: re.compile(_SQM),
    ConditionAttribute.SQML_LOCAL: re.compile(_SQM),
    ConditionAttribute.SEEING: re.compile(_SEEING),
    ConditionAttribute.SEEING_LOCAL: re.compile(_SEEING),
}


def condition_finding(key: ConditionAttribute, value: str) -> str | None:
    """Checks a condition value against its expected format.

    :param key: the Condition the value was given for
    :param value: the value to check
    :returns: a message when the value does not look like the condition it is given for, None otherwise
    """
    if not CONDITION_PATTERNS[key].fullmatch(value.strip()):
        return f"unusual {key} value '{value}'"
    return None
