"""`eval-ai` through cli.main over a copy of tests/fixtures/datadir with test sets written into it, the [ai] table
and the model server replaced by fakes (tests/unit/ai/fakes.py)."""
import json
import shutil

import pytest

from faint_fuzzies import cli
from faint_fuzzies.ai import client as ai_client
from faint_fuzzies.ai.evaluation import CASES_FILE, QUESTIONS_FILE
from faint_fuzzies.config import AiConfig
from tests.unit.ai.fakes import FakeClient
from tests.unit.builders import FIXTURES

RERANK = [{"search": "Staubband", "note": "Staubband deutlich.", "expected": "yes"}]
QUESTIONS = [{"question": "Messier 13 bitte", "filter": {"name_group": "M 13"}, "text": None}]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    client = FakeClient()
    client.answer = {"filter": {"name_group": ["Messier 13"]}, "text": None, "ignored": []}
    monkeypatch.setattr(cli, "read_ai_config", lambda: AiConfig("http://fake/v1", "chat", "model"))
    monkeypatch.setattr(ai_client, "AiClient", lambda url, timeout: client)
    return shutil.copytree(FIXTURES / "datadir", tmp_path / "datadir")


def write(data_dir, path, cases):
    (data_dir / path).parent.mkdir(parents=True, exist_ok=True)
    (data_dir / path).write_text(json.dumps(cases), encoding="utf-8")


def run(capsys, data_dir, *args):
    code = cli.main(["eval-ai", "--data-dir", str(data_dir), *args])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out else None, captured.err


def test_every_test_set_there_is_reported_under_its_name(capsys, data_dir):
    write(data_dir, CASES_FILE, RERANK)
    write(data_dir, QUESTIONS_FILE, QUESTIONS)
    code, result, _err = run(capsys, data_dir)
    assert code == cli.EXIT_OK
    assert (result["rerank"]["agree"], result["questions"]["agree"]) == (1, 1)


def test_only_measures_one_test_set(capsys, data_dir):
    write(data_dir, CASES_FILE, RERANK)
    write(data_dir, QUESTIONS_FILE, QUESTIONS)
    _code, result, _err = run(capsys, data_dir, "--only", "rerank")
    assert list(result) == ["rerank"]


def test_without_a_test_set_it_says_where_it_looked(capsys, data_dir):
    write(data_dir, CASES_FILE, RERANK)
    code, _result, err = run(capsys, data_dir, "--only", "questions")
    assert code == cli.EXIT_USAGE
    assert "questions.json" in err
