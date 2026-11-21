"""`filter --question` through cli.main, with the [ai] table and the model server replaced by fakes
(tests/unit/ai/fakes.py) over a copy of tests/fixtures/datadir; the fake chat model gives the answer a test sets."""
import json
import shutil

import pytest

from faint_fuzzies import cli
from faint_fuzzies.ai import client as ai_client
from faint_fuzzies.config import AiConfig
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES


@pytest.fixture
def fake(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(cli, "read_ai_config", lambda: AiConfig("http://fake/v1", "chat", "model"))
    monkeypatch.setattr(ai_client, "AiClient", lambda url, timeout: client)
    client.data_dir = shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")
    return client


def ask(capsys, fake, answer, *args, question="Kugelsternhaufen"):
    fake.answer = answer
    code = cli.main(["filter", "--data-dir", str(fake.data_dir), "--question", question, *args])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out else None, captured.err


def test_the_question_becomes_the_filter(capsys, fake):
    code, result, err = ask(capsys, fake, {"filter": {"type": ["GC"]}, "text": None, "ignored": []})
    assert code == cli.EXIT_OK
    assert [o["names"][0] for o in result["objects"]] == ["Messier 13"]
    assert result["question"] == {"asked": "Kugelsternhaufen", "criteria": ["type"], "filter": {"type": ["GC"]},
                                  "text": None, "ignored": []}
    assert 'filter {"type": ["GC"]}' in err
    assert "score" not in result["objects"][0]


def test_a_question_with_a_search_text_ranks_by_it(capsys, fake):
    _code, result, err = ask(capsys, fake, {"filter": {}, "text": "Doppelstern", "ignored": []}, "--no-rerank")
    assert result["objects"][0]["names"][0] == "STFA41"
    assert "score" in result["objects"][0]
    assert 'search "Doppelstern"' in err


def test_a_name_is_found_as_the_data_spells_it(capsys, fake):
    _code, result, _err = ask(capsys, fake, {"filter": {"name_group": ["M 13"]}, "text": None, "ignored": []})
    assert result["question"]["filter"]["name_group"] == ["M13"]
    assert [o["names"][0] for o in result["objects"]] == ["Messier 13"]


def test_what_could_not_be_expressed_is_warned_about(capsys, fake):
    code, _result, err = ask(capsys, fake, {"filter": {"type": ["GC"]}, "text": None, "ignored": ["im Winter"]})
    assert code == cli.EXIT_OK
    assert 'warning: ignored "im Winter"' in err


def test_an_unknown_name_fails_with_the_closest_ones(capsys, fake):
    code, result, err = ask(capsys, fake, {"filter": {"name_group": ["Messier 133"]}, "text": None, "ignored": []})
    assert code != cli.EXIT_OK and result is None
    assert "no object is named 'Messier 133'" in err


@pytest.mark.parametrize("args, message", [
    pytest.param(["--filter", "{}"], "replaces --filter and --search", id="with a filter"),
    pytest.param(["--search", "a"], "replaces --filter and --search", id="with a search"),
])
def test_a_question_takes_no_filter_or_search(capsys, fake, args, message):
    code, _result, err = ask(capsys, fake, {"filter": {}, "text": None, "ignored": []}, *args)
    assert code == cli.EXIT_USAGE
    assert message in err


def test_a_question_needs_a_data_dir(capsys, fake):
    code = cli.main(["filter", "--catalogue", "x.json", "--question", "Galaxien"])
    assert code == cli.EXIT_USAGE
    assert "--question needs --data-dir" in capsys.readouterr().err
