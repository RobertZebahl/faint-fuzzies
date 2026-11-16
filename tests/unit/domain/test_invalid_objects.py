"""The Invalid Objects a filter shows (domain/filters.py invalid_objects): they are at the error level, meet only the
criteria about the Object itself, and have no Observations. Fixture "problems_datadir"."""
import json

import pytest

from faint_fuzzies.domain.filters import FilterSpec, invalid_objects
from tests.unit.builders import FIXTURES, load_world


@pytest.fixture(scope="module")
def data():
    return load_world(FIXTURES / "problems_datadir")


def _invalid_matches(data, spec):
    found = invalid_objects(data.collection, FilterSpec.from_dict(json.loads(spec)), data.references,
                            data.observers, data.findings)
    return [o.label for o in found]


def test_the_invalid_objects_are_at_the_error_level(data):
    assert _invalid_matches(data, '{"finding": "error"}') == ["Unknown Type", "objects.json #3", "objects.json #4"]
    assert _invalid_matches(data, '{"finding": "warning"}') == []


def test_the_invalid_objects_meet_the_criteria_about_the_object(data):
    assert _invalid_matches(data, '{"name": "Unknown Type"}') == ["Unknown Type"]
    assert _invalid_matches(data, '{"type": "Gx"}') == ["objects.json #3"]


def test_the_invalid_objects_have_no_observations(data):
    assert _invalid_matches(data, '{"public": true}') == []
    assert _invalid_matches(data, '{"seen": "seen"}') == []
