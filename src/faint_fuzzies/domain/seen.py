"""Whether an Object counts as seen, from its (or given) private observations."""
from collections.abc import Iterable
from enum import Enum

from faint_fuzzies.domain.model import Object, ObjectType
from faint_fuzzies.domain.observation import (
    FAILED_FROM_DEEP_SKY,
    FAILED_FROM_DOUBLE_STAR,
    Difficulty,
    Grade,
    Observation,
    Result,
)


class SeenStatus(Enum):
    """Whether an Object has been observed at all, and if so, whether it was ever actually seen."""
    NOT_OBSERVED = "not_observed"
    FAILED = "failed"
    SEEN = "seen"


def seen_status(obj: Object, observations: Iterable[Observation] | None = None) -> SeenStatus:
    """Judged by the private observations only: those of the Object, or the given ones (for example
    with the observations of referenced Objects added). An observation without a grade counts as
    seen, and the best reading of an observation and of an Object wins.

    :param obj: the object to judge
    :param observations: the observations to judge by, instead of `obj`'s own
    :returns: the object's seen status
    """
    double_star = ObjectType.DOUBLE_STAR in obj.types
    private = [o for o in (obj.observations if observations is None else observations) if not o.public]
    if not private:
        return SeenStatus.NOT_OBSERVED
    if any(is_observation_seen(o, double_star) for o in private):
        return SeenStatus.SEEN
    return SeenStatus.FAILED


def is_observation_seen(observation: Observation, double_star: bool) -> bool:
    """Whether `observation` counts as seen: an observation without a grade does, and otherwise the best
    reading among its visibility entries wins.

    :param observation: the observation to judge
    :param double_star: whether the object observed is a double star (the two kinds grade differently)
    :returns: whether the observation counts as seen
    """
    if not observation.visibility:
        return True
    return any(e.result is None or _is_result_seen(e.result, double_star) for e in observation.visibility)


def _is_result_seen(result: Result, double_star: bool) -> bool:
    """Whether one visibility entry's result counts as seen.

    :param result: the result to judge
    :param double_star: whether the object observed is a double star
    :returns: whether the result counts as seen
    """
    if isinstance(result, Grade):
        # a range such as "4-5" is read at its better end
        return result.low < (FAILED_FROM_DOUBLE_STAR if double_star else FAILED_FROM_DEEP_SKY)
    return result is not Difficulty.FAILED
