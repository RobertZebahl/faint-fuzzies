"""The Browse page's Question field: what it says about the model server, and the Match column of a Description
search's results (ui/question_bar.py, ui/browse.py)."""
from types import SimpleNamespace

from faint_fuzzies.ai.service import AiState
from faint_fuzzies.ui.browse import OBJECT_COLUMNS, _match_columns, _match_text
from faint_fuzzies.ui.question_bar import ignored_text, status_text


def service(state, progress=("Starting the model server…", 0.0), message=""):
    return SimpleNamespace(state=state, progress=progress, message=message)


def test_the_field_tells_what_the_server_is_doing():
    assert status_text(service(AiState.STARTING), busy=False) == "Starting the model server…"
    assert status_text(service(AiState.INDEXING, ("Embedding 120 new description texts", 0.25)), busy=False) == \
        "Embedding 120 new description texts 25%"
    assert status_text(service(AiState.READY, ("Judging 40 notes with chat", 0.5)), busy=True) == \
        "Judging 40 notes with chat 50%"


def test_a_ready_server_needs_no_words_and_a_failed_one_says_why():
    assert status_text(service(AiState.READY), busy=False) is None
    assert status_text(service(AiState.FAILED, message="cannot start the model server"), busy=False) == \
        "cannot start the model server"


def test_what_a_question_could_not_express_is_named():
    assert ignored_text(("Bright", "in summer")) == \
        "Not expressed: 'Bright', 'in summer' - the result may be broader than asked"


def test_the_match_column_ranks_the_results_in_the_searchs_order():
    results = [SimpleNamespace(verdict="yes", score=0.712), SimpleNamespace(verdict="partly", score=0.75)]
    assert _match_columns(results, 1) == {"match": "partly 0.75", "match_rank": 1}
    assert _match_columns(None, 0) == {"match": "", "match_rank": None}
    assert _match_text(None, 0.6) == "0.60"


def test_the_match_column_comes_last_and_sorts_by_rank():
    assert OBJECT_COLUMNS[-1] == {"name": "match", "label": "Match", "field": "match_rank", "align": "center",
                                  "sortable": True}
