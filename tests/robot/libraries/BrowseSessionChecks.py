# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""BrowsePage's session-reselection-after-reload lookup (ui/browse.py: _find_session_by_key, _session_key),
without a browser: a Reload replaces every Session object, so the previously-selected one has to be found
again by its start time rather than by identity."""
from datetime import datetime

from faint_fuzzies.domain.session import Location, Session
from faint_fuzzies.ui.browse import _find_session_by_key, _session_key

_LOCATION = Location("Home", 50.0, 10.0, 100, 1)


def _session(start_text):
    start = datetime.fromisoformat(start_text)
    return Session({}, start, start, _LOCATION, {})


def session_key(start_text):
    return _session_key(_session(start_text))


def found_after_reload(selected_start, new_starts):
    """Simulates a Reload: `new_starts` are brand-new Session objects (as a real Reload makes), none of them
    the same object as the one `selected_start` was selected on. Returns the start time of the one found, or
    None."""
    key = session_key(selected_start)
    new_sessions = [_session(start) for start in new_starts]
    found = _find_session_by_key(new_sessions, key)
    return None if found is None else _session_key(found)


def not_the_same_object_even_when_found():
    """The found Session is a different object from the one selected before - exactly what a Reload
    produces - and still matches by key."""
    selected = _session("2026-09-01T20:00")
    replacement = _session("2026-09-01T20:00")
    found = _find_session_by_key([replacement], _session_key(selected))
    return found is replacement and found is not selected
