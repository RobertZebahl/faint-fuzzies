"""The values of an observation (domain/observation.py), as the own catalogue's values are checked on loading."""
import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from tests.unit.builders import FIXTURES, write_catalogue


@pytest.mark.parametrize(("object_type", "visibility", "message"), [
    ("Gx", "5-4", "visibility result '5-4' is a reversed range"),
    ("Gx", "1-3", "visibility result '1-3' is not a range of two adjacent grades for this scale"),
    ("Gx", "5-6", "visibility result '5-6' is not a range of two adjacent grades for this scale"),
    ("Gx", "5*", "invalid visibility result '5*'"),
    ("Gx", "4-5*", "invalid visibility result '4-5*'"),
    ("**", "4", "invalid visibility result '4' for a double star"),
    ("**", "2-3", "visibility result '2-3' is not a range of two adjacent grades for a double star"),
    ("**", "3*", "invalid visibility result '3*'"),
])
def test_a_grade_must_fit_its_scales_shape(tmp_path, object_type, visibility, message):
    """A range is only ever two adjacent grades that stop at the last "seen" one (5 for any other Object, 2 for a
    double star); a reversed range is rejected as a likely typo rather than silently reordered; a trailing "*" is
    not part of the grammar at all, not even on the bare grade 5."""
    path = write_catalogue(tmp_path, "grades.json", [
        {"NAME": "X", "TYPE": object_type, "OBSERVATIONS": [{"OPTIC": "A", "VISIBILITY": visibility}]}])
    assert [(f.attribute, f.severity, f.message) for f in load_catalogue(path).findings] == [
        ("VISIBILITY", "error", message)]


def test_spaces_inside_observation_values_are_tolerated():
    """The writer removes them, so the loader ignores them: "B, 10x50" is valid."""
    assert not [f for f in load_catalogue(FIXTURES / "unformatted.json").findings if f.severity == "error"]
