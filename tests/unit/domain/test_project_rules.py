"""The project lists' own rules (domain/lists.py: build_list): the list tags and the user's own rating of a system are
kept on its pairs, the orbit list, and a rating counts whatever the instrument of the rated row.

SYS1's pair carries tags B and C and the rating 3; SYS2 has a pair with an observation and another without; SYS3 has
a note only.
"""
import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.lists import LISTS, build_list
from faint_fuzzies.domain.observation import Observation, parse_optic
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.domain.references import References
from tests.unit.builders import write_catalogue

SEEN = {"OPTIC": "B,10x50", "VISIBILITY": "EASY", "DESCRIPTION_DE": "Ein", "DESCRIPTION_EN": "One"}
OWN = [
    {"GROUP": "SYS1", "TYPE": "**", "CONSTELLATION": "Lyr"},
    {"NAME": "PAIR1", "GROUP": "SYS1", "TYPE": "**", "CONSTELLATION": "Lyr", "COMPONENT": "AB",
     "COORDINATES": "180000,+300000", "PROJECT_DOUBLE_STARS_LISTS": "BC", "RATING": 3, "OBSERVATIONS": [SEEN]},
    {"NAME": "PAIR2", "GROUP": "SYS1", "TYPE": "**", "CONSTELLATION": "Lyr", "COMPONENT": "AC",
     "COORDINATES": "180000,+300000"},
    {"GROUP": "SYS2", "TYPE": "**", "CONSTELLATION": "Cyg"},
    {"NAME": "PAIR3", "GROUP": "SYS2", "TYPE": "**", "CONSTELLATION": "Cyg", "COMPONENT": "AB",
     "COORDINATES": "200000,+400000"},
    {"NAME": "PAIR4", "GROUP": "SYS2", "TYPE": "**", "CONSTELLATION": "Cyg", "COMPONENT": "AC",
     "COORDINATES": "200000,+400000", "OBSERVATIONS": [SEEN]},
    {"GROUP": "SYS3", "TYPE": "**", "CONSTELLATION": "Her"},
    {"NAME": "PAIR5", "GROUP": "SYS3", "TYPE": "**", "CONSTELLATION": "Her", "COMPONENT": "AB",
     "COORDINATES": "170000,+100000", "OBSERVATIONS": [{"DESCRIPTION_DE": "Kopf", "DESCRIPTION_EN": "Header"}]},
    {"NAME": "Messier 99", "TYPE": "GX", "CONSTELLATION": "Com", "COORDINATES": "122318,+144500",
     "OBSERVATIONS": [SEEN]},
]
DOUBLE_STARS = "project-double-stars"
DEEP_SKY_WITH_BINOCULARS = "project-deep-sky-with-binoculars"


@pytest.fixture
def own(tmp_path):
    return write_catalogue(tmp_path, "own.json", OWN)


def _project_lists(catalogue, project, orbit_pairs=(), community=()):
    """{label of the entry: its sublists (without the right ascension bands) and its stars}. `orbit_pairs` are names
    of pairs that have an orbit diagram; `community` are (object name, observer id, import format, optic code, rating)
    of observations of other observers."""
    collection = Collection([load_catalogue(catalogue)])
    by_name = {name: obj for obj in collection.objects for name in obj.names}
    for name, observer, format_name, optic, rating in community:
        by_name[name].community_observations.append(Observation(
            {}, public=True, optic=parse_optic(optic), visibility=(), observer=Observer(observer, "A", "B"),
            rating=rating, format=format_name))
    orbits = frozenset(id(by_name[name]) for name in orbit_pairs)
    result = build_list(LISTS[project], collection, References(collection), None, orbits)
    return {e.unit.label: {"lists": sorted(s for s in e.sublists if not s.startswith("ra-")),
                           "stars": e.rounded_rating} for e in result.entries}


def test_tags_and_the_users_rating_of_a_pair_count_for_its_system(own):
    lists = _project_lists(own, DOUBLE_STARS)
    assert lists["SYS1"]["lists"] == ["best-of", "binoculars", "colored", "complete", "recommendations"]
    assert lists["SYS1"]["stars"] == 3


def test_the_orbit_list_needs_an_orbit_diagram_and_an_observation(own):
    """SYS2 has an orbit on a pair that has no observation, but the system has one; SYS3 has an orbit but only a
    note, no observation, so it is not published in the project at all."""
    lists = _project_lists(own, DOUBLE_STARS, ["PAIR1", "PAIR3", "PAIR5"])
    assert "orbits" in lists["SYS1"]["lists"]
    assert "orbits" in lists["SYS2"]["lists"]
    assert "SYS3" not in lists


def test_without_an_orbit_there_is_no_orbit_list(own):
    assert "orbits" not in _project_lists(own, DOUBLE_STARS)["SYS1"]["lists"]


def test_a_rating_counts_whatever_the_instrument_of_the_rated_row(own):
    """Deep Sky With Binoculars keeps binocular observations only, but a rating of the object is a rating of the
    object: a telescope row of the Global observer rated with three stars makes it best-of."""
    lists = _project_lists(own, DEEP_SKY_WITH_BINOCULARS, community=[("Messier 99", "dana-example", "global",
                                                                      "N,200,1200", 3)])
    assert lists["Messier 99"]["stars"] == 3
    assert "best-of" in lists["Messier 99"]["lists"]
