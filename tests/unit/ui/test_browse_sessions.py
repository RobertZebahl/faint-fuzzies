"""The Browse page and Sessions.

After a Reload, BrowsePage._on_reloaded restores a selected Session by looking it up again by its start time
(_session_key), since Reload replaces every Session object: adding observations to a session step by step should
not mean re-selecting it after every Reload.

With a Session selected, BrowsePage._apply_filter sorts the Objects table by _earliest_in_session,
earliest-observed-first - the order a session was actually observed in. A community observation has no own start
(dated by its Session only, see Observation.start), so it falls back to the Session's own start.
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from faint_fuzzies.ui.browse import _earliest_in_session, _find_session_by_key, _session_key
from tests.unit.builders import session


def _found_after_reload(selected_start, new_starts):
    """The start of the Session found among brand-new Session objects (as a real Reload makes), or None."""
    found = _find_session_by_key([session(start) for start in new_starts], _session_key(session(selected_start)))
    return None if found is None else _session_key(found)


def test_the_session_with_a_matching_start_time_is_found_among_the_new_ones():
    found = _found_after_reload("2026-09-01T20:00", ["2026-08-31T19:00", "2026-09-01T20:00", "2026-09-02T21:00"])
    assert found == "2026-09-01T20:00"


def test_the_found_session_is_a_new_object_not_the_one_that_was_selected_before():
    """A Reload always builds brand-new Session objects; matching by identity would never work."""
    selected = session("2026-09-01T20:00")
    replacement = session("2026-09-01T20:00")
    found = _find_session_by_key([replacement], _session_key(selected))
    assert found is replacement
    assert found is not selected


def test_nothing_is_found_when_the_session_is_gone_after_reload():
    """Deleted, or its start time edited - either way _on_reloaded falls back to no selection."""
    assert _found_after_reload("2026-09-01T20:00", ["2026-09-02T21:00"]) is None


def test_nothing_is_found_in_an_empty_sessions_list():
    assert _found_after_reload("2026-09-01T20:00", []) is None


def _match(*starts):
    """A Match-like object whose observations start at `starts` (None for a community observation with no own
    start)."""
    return SimpleNamespace(observations=tuple(
        SimpleNamespace(observation=SimpleNamespace(start=datetime.fromisoformat(s) if s else None)) for s in starts))


@pytest.mark.parametrize(("observation_starts", "expected"), [
    pytest.param(["2026-09-01T21:15"], "2026-09-01T21:15:00",
                 id="a single observation sorts by its own start"),
    pytest.param(["2026-09-01T23:00", "2026-09-01T21:15"], "2026-09-01T21:15:00",
                 id="an object observed twice sorts by the earlier of the two"),
    pytest.param([None], "2026-09-01T20:00:00",
                 id="a community observation with no own start falls back to the session's start"),
    # The Session's own start is always at or before every observation within it, so a community observation
    # (falling back to it) sorts no later than a timed one.
    pytest.param(["2026-09-01T21:15", None], "2026-09-01T20:00:00",
                 id="a mix falls back to the session's start when it is the earliest"),
])
def test_earliest_in_session(observation_starts, expected):
    key = _earliest_in_session(_match(*observation_starts), session("2026-09-01T20:00"))
    assert key.isoformat() == expected
