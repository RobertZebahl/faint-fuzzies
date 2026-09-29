# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""BrowsePage's sort key for the Objects table when a Session is selected (ui/browse.py:
_earliest_in_session), without a browser: the key is the earliest of a Match's (already
session-filtered) observations, falling back to the Session's own start for a community
observation (dated by its Session only, never its own start - see Observation.start)."""
from datetime import datetime
from types import SimpleNamespace

from faint_fuzzies.domain.session import Location, Session
from faint_fuzzies.ui.browse import _earliest_in_session

_LOCATION = Location("Home", 50.0, 10.0, 100, 1)


def _session(start_text, end_text=None):
    start = datetime.fromisoformat(start_text)
    end = datetime.fromisoformat(end_text) if end_text else start
    return Session({}, start, end, _LOCATION, {})


def _match(*starts):
    """A Match-like object whose observations are given by `starts` (each a start time text, or None for
    a community observation with no own start)."""
    observations = tuple(SimpleNamespace(observation=SimpleNamespace(
        start=datetime.fromisoformat(s) if s else None)) for s in starts)
    return SimpleNamespace(observations=observations)


def earliest_in_session(session_start, *observation_starts):
    """:param session_start: the selected Session's own start
    :param observation_starts: the start of each of the Match's observations within it, None for a
        community observation with no own start
    :returns: the key _earliest_in_session gives it, as isoformat text
    """
    session = _session(session_start)
    match = _match(*observation_starts)
    return _earliest_in_session(match, session).isoformat()
