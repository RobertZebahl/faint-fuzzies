"""`filter --search` through cli.main, with the [ai] table and the model server replaced by fakes
(tests/unit/ai/fakes.py) over a copy of tests/fixtures/datadir."""
import json
import shutil

import pytest

from faint_fuzzies import cli
from faint_fuzzies.ai import client as ai_client
from faint_fuzzies.config import AiConfig
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "read_ai_config", lambda: AiConfig("http://fake/v1", "chat", "model"))
    monkeypatch.setattr(ai_client, "AiClient", lambda url, timeout: FakeClient())
    return shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")


def run(capsys, *args):
    code = cli.main(["filter", *args])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out else None, captured.err


def test_the_objects_come_ranked_with_their_scores(capsys, data_dir):
    code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Kugelhaufen")
    assert code == cli.EXIT_OK
    first = result["objects"][0]
    assert first["names"][0] == "Messier 13"
    assert first["score"] == max(o["score"] for o in first["observations"] if o["score"] is not None)
    assert [o["score"] is None for o in first["observations"]].count(False) == 2


def test_names_only_lists_the_ranked_names(capsys, data_dir):
    _code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Doppelstern", "--names-only")
    assert result["objects"][0] == "STFA41"


def test_the_filter_narrows_the_search(capsys, data_dir):
    _code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Doppelstern",
                              "--filter", '{"name": "IC348"}')
    assert result == {"count": 0, "objects": []}


def test_the_limit_and_min_score_options_override_the_config(capsys, data_dir):
    _code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Text",
                              "--min-score", "0", "--limit", "1")
    assert result["count"] == 1


def test_the_index_is_cached_in_the_data_directory(capsys, data_dir):
    run(capsys, "--data-dir", str(data_dir), "--search", "Kugelhaufen")
    assert list((data_dir / "cache" / "ai").glob("embeddings-*.npz"))


@pytest.mark.parametrize("args, message", [
    pytest.param(["--catalogue", "x.json", "--search", "a"], "needs --data-dir", id="without data dir"),
    pytest.param(["--data-dir", "d", "--search", " "], "needs a text", id="empty text"),
    pytest.param(["--data-dir", "d", "--limit", "3"], "only go with --search", id="limit alone"),
    pytest.param(["--data-dir", "d", "--no-rerank"], "only go with --search", id="no rerank alone"),
    pytest.param(["--data-dir", "d", "--search", "a", "--min-score", "1.5"], "between -1 and 1", id="bad score"),
])
def test_wrong_search_options_are_usage_errors(capsys, data_dir, args, message):
    code, _result, err = run(capsys, *args)
    assert code == cli.EXIT_USAGE
    assert message in err


def test_without_an_ai_table_search_says_where_it_belongs(capsys, data_dir, monkeypatch):
    monkeypatch.setattr(cli, "read_ai_config", lambda: None)
    code, _result, err = run(capsys, "--data-dir", str(data_dir), "--search", "a")
    assert code == cli.EXIT_USAGE
    assert "needs an [ai] table" in err


def test_reranking_gives_each_hit_and_object_its_verdict(capsys, data_dir):
    _code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Kugelhaufen")
    first = result["objects"][0]
    assert first["verdict"] == "yes"
    assert all(o["verdict"] == ("yes" if o["score"] is not None else None) for o in first["observations"])


def test_no_rerank_ranks_by_the_embeddings_alone(capsys, data_dir):
    _code, result, _err = run(capsys, "--data-dir", str(data_dir), "--search", "Kugelhaufen", "--no-rerank")
    first = result["objects"][0]
    assert "verdict" not in first and all("verdict" not in o for o in first["observations"])
