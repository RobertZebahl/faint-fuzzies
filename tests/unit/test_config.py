"""The [ai] table of the config file, written to a temporary config file for each test."""
import pytest

from faint_fuzzies import config
from faint_fuzzies.config import AiConfig, read_ai_config
from faint_fuzzies.domain.findings import CatalogueError

MINIMAL = 'url = "http://localhost:11434/v1/"\nchat_model = "chat"\nembedding_model = "bge-m3"\n'


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    monkeypatch.setattr(config, "CONFIG_PATH", path)
    return path


def test_without_a_config_file_there_is_no_ai(config_file):
    assert read_ai_config() is None


def test_without_an_ai_table_there_is_no_ai(config_file):
    config_file.write_text('data_dir = "/data"\n', encoding="utf-8")
    assert read_ai_config() is None


def test_the_defaults_fill_what_the_table_leaves_out_and_the_url_loses_its_slash(config_file):
    config_file.write_text("[ai]\n" + MINIMAL, encoding="utf-8")
    assert read_ai_config() == AiConfig("http://localhost:11434/v1", "chat", "bge-m3")


def test_the_numbers_can_be_set(config_file):
    config_file.write_text("[ai]\n" + MINIMAL + "min_score = 0.3\nlimit = 20\ntimeout = 60\n", encoding="utf-8")
    ai = read_ai_config()
    assert (ai.min_score, ai.limit, ai.timeout) == (0.3, 20, 60.0)


@pytest.mark.parametrize("table, message", [
    pytest.param('url = "x"\n', "chat_model, embedding_model", id="missing models"),
    pytest.param(MINIMAL + "limit = 0\n", "greater than 0", id="limit zero"),
    pytest.param(MINIMAL + "min_score = 2\n", "between -1 and 1", id="score out of range"),
    pytest.param(MINIMAL + 'limit = "10"\n', "must be a whole number", id="limit as text"),
    pytest.param(MINIMAL + "limit = 2.5\n", "must be a whole number", id="limit as fraction"),
])
def test_an_invalid_ai_table_is_an_error(config_file, table, message):
    config_file.write_text("[ai]\n" + table, encoding="utf-8")
    with pytest.raises(CatalogueError, match=message):
        read_ai_config()
