"""Private observations are assigned to their session (domain/session.py)."""
from faint_fuzzies.domain.session import load_sessions
from tests.unit.builders import FIXTURES, filter_matches


def test_overlapping_sessions_use_the_earliest():
    """The fixture's last two sessions overlap, and NGC3's observation is in both of them."""
    (match,) = filter_matches('{"name": "NGC3"}', FIXTURES / "observations.json",
                              sessions=load_sessions(FIXTURES / "sessions.json"))
    assert match.observations[0].observation.session.start.isoformat(timespec="minutes") == "2011-10-03T20:00"
