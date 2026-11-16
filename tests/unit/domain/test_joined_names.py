"""A name that joins several ("NGC6992 & NGC6995 & IC1340") is also the name of each of them, in the index of names
and in the groups; the parts do not find it the other way round, since observers write the parts."""
import pytest

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import OTHER
from tests.unit.builders import write_catalogue

OWN = [
    {"NAME": "NGC6992 & NGC6995 & IC1340, Eastern Veil", "GROUP": "Veil A & Veil B", "TYPE": "BN",
     "CONSTELLATION": "Cyg", "COORDINATES": "205630,+312300"},
    {"NAME": "NGC1", "GROUP": "Veil A & Veil B", "TYPE": "Gx", "CONSTELLATION": "Peg", "COORDINATES": "000000,+000000"},
    {"GROUP": "Twin X & Twin Y", "TYPE": "OC", "CONSTELLATION": "Cas", "COORDINATES": "000000,+000000"},
]
JOINED = "NGC6992 & NGC6995 & IC1340"


@pytest.fixture(scope="module")
def collection(tmp_path_factory):
    return Collection([load_catalogue(write_catalogue(tmp_path_factory.mktemp("joined"), "own.json", OWN))])


def _found_by(collection, kind, name):
    """The first names of the Objects found under `name`, each once (the index may repeat one)."""
    return sorted({id(o): o.label for o in collection.names.lookup(kind, name)}.values())


@pytest.mark.parametrize("name", ["NGC6992", "NGC6995", "IC1340", "Eastern Veil", "NGC 6992", JOINED])
def test_each_part_of_a_joined_name_finds_the_object(collection, name):
    assert _found_by(collection, OTHER, name) == [JOINED]


def test_the_joined_name_is_not_found_by_only_a_part_of_it_written_differently(collection):
    assert _found_by(collection, OTHER, "NGC6993") == []


def test_parts_of_a_joined_group_name_are_group_names(collection):
    assert len(collection.groups_named(0, "Twin Y")) == 1
    assert len(collection.members_named(0, "Veil B")) == 2
