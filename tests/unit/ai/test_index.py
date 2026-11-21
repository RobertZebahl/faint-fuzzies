"""The description index: which texts it embeds, and that its cache in the data directory spares the model
server every text it has seen before. The fixture is a copy of tests/fixtures/datadir, whose own and community
observations carry a few short Descriptions and Notes."""
import shutil

import pytest

from faint_fuzzies.ai.index import description_texts, index_path, update_index
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES, find_object, load_world


@pytest.fixture
def data_dir(tmp_path):
    return shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")


@pytest.fixture
def world(data_dir):
    return load_world(data_dir)


def replace_description(world, label, text):
    """Gives the observation of `label` that has Descriptions the one Description `text` instead."""
    record = next(observation.record for observation in find_object(world.collection, label).all_observations
                  if observation.descriptions)
    for key in [key for key in record if key.startswith("DESCRIPTION")]:
        del record[key]
    record["DESCRIPTION"] = text


def all_texts(world):
    return {text for obj in world.collection.objects for observation in obj.all_observations
            for text in description_texts(observation)}


def test_an_observation_with_the_same_german_and_english_text_gives_it_once(world):
    texts = [description_texts(observation) for observation in find_object(world.collection, "STF999").all_observations]
    assert ("Einzeln", "Single") in texts


def test_the_notes_of_an_observation_are_searched_as_well(world):
    texts = [description_texts(observation) for observation in find_object(world.collection, "STFA41").all_observations]
    assert ("Deutscher Text", "English text", "Meine private Notiz") in texts


def test_the_first_update_embeds_every_distinct_text_once(data_dir, world):
    client = FakeClient()
    index = update_index(data_dir, world.collection.objects, client, "model-a")
    assert sorted(client.embedded) == sorted(all_texts(world))
    assert len(index.rows) == len(all_texts(world))
    assert index_path(data_dir, "model-a").is_file()


def test_a_second_update_asks_the_server_for_nothing(data_dir, world):
    update_index(data_dir, world.collection.objects, FakeClient(), "model-a")
    client = FakeClient()
    index = update_index(data_dir, world.collection.objects, client, "model-a")
    assert client.embedded == []
    assert index.row_of("Kugelhaufen") is not None


def test_only_a_new_text_is_embedded_and_a_gone_one_is_dropped(data_dir, world):
    update_index(data_dir, world.collection.objects, FakeClient(), "model-a")
    replace_description(world, "NGC752", "Ein neuer Text")
    client = FakeClient()
    index = update_index(data_dir, world.collection.objects, client, "model-a")
    assert client.embedded == ["Ein neuer Text"]
    assert index.row_of("Beschreibung ohne Bild") is None


def test_each_model_has_a_cache_of_its_own(data_dir, world):
    update_index(data_dir, world.collection.objects, FakeClient(), "model-a")
    client = FakeClient()
    update_index(data_dir, world.collection.objects, client, "model:b")
    assert sorted(client.embedded) == sorted(all_texts(world))
    assert index_path(data_dir, "model-a").is_file() and index_path(data_dir, "model:b").is_file()


def test_vectors_of_another_length_under_the_same_model_name_rebuild_the_cache(data_dir, world):
    update_index(data_dir, world.collection.objects, FakeClient(), "model-a")
    replace_description(world, "NGC752", "Ein neuer Text")
    client = FakeClient(extra=(0.5,))
    index = update_index(data_dir, world.collection.objects, client, "model-a")
    assert set(client.embedded) >= all_texts(world)
    assert index.vectors.shape[1] == 10


def test_an_unreadable_cache_file_is_rebuilt_without_an_error(data_dir, world):
    path = index_path(data_dir, "model-a")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a cache")
    client = FakeClient()
    update_index(data_dir, world.collection.objects, client, "model-a")
    assert sorted(client.embedded) == sorted(all_texts(world))
