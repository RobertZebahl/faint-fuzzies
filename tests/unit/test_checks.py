"""The checks across a whole collection (checks.py)."""
from faint_fuzzies.checks import constellation_findings
from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from tests.unit.builders import write_catalogue

VEGA = "183656.30,+384701.00"  # J2000.0, in Lyr
M33_B1950 = "013101.00,+302400.00"  # in Tri


def test_a_constellation_must_match_the_one_computed_from_the_objects_own_coordinates(tmp_path):
    """An Object without coordinates or without a constellation is not checked here (with --data-dir, missing ones
    get their own check). B1950 coordinates are read in the B1950/FK4 frame."""
    catalogue = load_catalogue(write_catalogue(tmp_path, "own.json", [
        {"NAME": "GOOD1", "TYPE": "Gx", "CONSTELLATION": "Lyr", "COORDINATES": VEGA},
        {"NAME": "WRONG1", "TYPE": "Gx", "CONSTELLATION": "Her", "COORDINATES": VEGA},
        {"NAME": "NOCONST1", "TYPE": "Gx", "COORDINATES": VEGA},
        {"NAME": "NOCOORD1", "TYPE": "Gx", "CONSTELLATION": "Lyr"},
        {"NAME": "B1950GOOD", "TYPE": "Gx", "CONSTELLATION": "Tri", "COORDINATES": M33_B1950, "EQUINOX": "B1950"},
        {"NAME": "B1950WRONG", "TYPE": "Gx", "CONSTELLATION": "Psc", "COORDINATES": M33_B1950, "EQUINOX": "B1950"},
    ]))
    assert not catalogue.findings
    wrong, b1950_wrong = constellation_findings(Collection([catalogue]))
    assert (wrong.object, wrong.attribute, wrong.severity) == ("WRONG1", "CONSTELLATION", "warning")
    assert "constellation Her does not match Lyr" in wrong.message
    assert b1950_wrong.object == "B1950WRONG"
    assert "constellation Psc does not match Tri" in b1950_wrong.message
