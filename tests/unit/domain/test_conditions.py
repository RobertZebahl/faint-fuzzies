"""The observing conditions of a session (domain/conditions.py), checked when the sessions file is loaded."""
import json

import pytest

from faint_fuzzies.domain.session import load_sessions


def _findings(tmp_path, **conditions):
    """The findings of a sessions file with one session that has `conditions`."""
    path = tmp_path / "sessions.json"
    path.write_text(json.dumps([{"DATE": "01.01.2020", "TIME": "20:00-21:00", "LOCATION": "A;1;2;3;1", **conditions}]),
                    encoding="utf-8")
    return load_sessions(path).findings


def test_a_bortle_range_may_carry_a_tendency_on_either_side(tmp_path):
    """"6--7" is "6-" to "7": each side of a range may carry its own "+"/"-" independently, not just the value as a
    whole."""
    assert not _findings(tmp_path, BORTLE="6--7")


@pytest.mark.parametrize(("attribute", "value"), [("NELM", "15.34"), ("SQM", "5.5"), ("SQML", "21.34")])
def test_nelm_sqm_and_sqm_l_accept_any_positive_number(tmp_path, attribute, value):
    """More digits than the usual one before, or two after, the decimal point are not "unusual" - a real reading is
    never bound to a fixed width."""
    assert not _findings(tmp_path, **{attribute: value})


def test_an_unusual_seeing_value_is_a_warning(tmp_path):
    """SEEING follows the fixed "n/5" (or "a-b/5") shape unlike NELM/SQM/SQM-L, so a value that does not fit it at
    all is still flagged."""
    (finding,) = _findings(tmp_path, SEEING="bad")
    assert (finding.attribute, finding.severity) == ("SEEING", "warning")
    assert "unusual SEEING value 'bad'" in finding.message
