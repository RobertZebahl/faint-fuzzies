"""The Findings of a loaded data directory, by the Object they concern (fixture "problems_datadir"). An Object with an
error is Invalid: it is kept apart from the Collection, known by its place when it has no name, and shown with its
Findings. An Observation with an error is left out of its Object, which stays valid and is marked, even when none is
left. The checks that need several records or files are made when loading and give their Findings to the Objects
too."""
import pytest

from tests.unit.builders import FIXTURES, load_world


@pytest.fixture(scope="module")
def world():
    data = load_world(FIXTURES / "problems_datadir")
    own = data.collection.catalogues[0]
    return data, own


def _object(world, label):
    _data, own = world
    return next(o for o in [*own.objects, *own.invalid] if o.label == label)


def _severity(world, label):
    data, _own = world
    return data.findings.severity(_object(world, label))


def _findings(world, label):
    """(severity, attribute, observation, message) of each Finding of the Object."""
    data, _own = world
    return [(p.severity, p.attribute, p.observation, p.message) for p in data.findings.get_findings(_object(world, label))]


def _in_collection(world):
    data, own = world
    return [o.label for o in data.collection.objects if o.catalogue == own.name]


def _left_out_observations(world, label):
    return [number for number, _raw in _object(world, label).invalid_observations]


def test_an_object_with_an_error_is_kept_apart_from_the_collection(world):
    _data, own = world
    assert [o.label for o in own.invalid] == ["Unknown Type", "objects.json #3", "objects.json #4"]
    assert _in_collection(world) == ["Fine", "Half Bad", "Only Bad", "Missing Sketch", "Warned", "Not Placed"]


def test_a_record_without_a_name_is_known_by_its_place(world):
    """A record that is no JSON object keeps what it was."""
    assert _object(world, "objects.json #4").raw == "just some text"
    assert [f[3] for f in _findings(world, "objects.json #3")] == ["record has neither NAME nor GROUP"]


def test_an_invalid_object_has_an_error_and_its_findings(world):
    assert _severity(world, "Unknown Type") == "error"
    assert [f[3] for f in _findings(world, "Unknown Type")] == ["unknown object type 'Zz'"]


def test_an_observation_with_an_error_is_left_out_but_its_object_stays(world):
    """The Object has an error marker, since an Observation of it is missing, and keeps the other one."""
    assert _severity(world, "Half Bad") == "error"
    assert _left_out_observations(world, "Half Bad") == [1]
    assert [(f[2], f[1]) for f in _findings(world, "Half Bad")] == [(1, "OPTIC")]


def test_an_object_with_only_invalid_observations_stays_valid_and_is_marked(world):
    """It has nothing to publish, but that is no reason to hide it: it keeps its error marker."""
    _data, own = world
    assert "Only Bad" not in [o.label for o in own.invalid]
    assert "Only Bad" in _in_collection(world)
    assert _severity(world, "Only Bad") == "error"
    assert _left_out_observations(world, "Only Bad") == [1]


def test_a_warning_marks_an_object_and_leaves_it_valid(world):
    _data, own = world
    assert _severity(world, "Warned") == "warning"
    assert "Warned" in [o.label for o in own.objects]


def test_an_object_without_findings_has_none(world):
    assert _severity(world, "Fine") is None
    assert _findings(world, "Fine") == []


def test_the_checks_of_several_records_give_their_findings_to_the_objects(world):
    """A sketch file that is not there, and an Object of the Global list without coordinates. They mark the Object,
    which stays in the Collection."""
    assert [(f[0], f[1], f[3]) for f in _findings(world, "Missing Sketch")] == [
        ("error", "SKETCH", "file 'gone.jpg' not found in sketches/")]
    assert _severity(world, "Missing Sketch") == "error"
    assert [(f[0], f[1]) for f in _findings(world, "Not Placed")] == [("error", "COORDINATES")]
    assert "Not Placed" in _in_collection(world)
