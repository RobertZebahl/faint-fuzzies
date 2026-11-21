"""Measuring the chat model against test sets the user has written by hand, so a change of prompt or model shows
in numbers rather than by comparing results by eye. Both live in the data directory, never in the repository:
the first holds observation texts, the user's own and the community's, and the second names observers.

::

    <data-dir>/observations/owner/ai_eval/rerank.json
    <data-dir>/observations/owner/ai_eval/questions.json

rerank.json is a JSON list of judged notes, each {"search": ..., "note": ..., "expected": "yes" | "partly" |
"no"} and optionally "object" (only shown in the report). questions.json is a JSON list of Questions, each
{"question": ..., "filter": {the expected FilterSpec}, "text": the expected search text or null} and optionally
"ignored" (only shown): the filter must come out the same (a list's order does not matter, a single value is a
list of one, names are compared by the Objects they find), the text only there or not, since many texts are right.
"""
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.question import Context, QuestionError, ask, resolve_names
from faint_fuzzies.ai.rerank import BATCH_SIZE, VERDICTS, judge_notes, rubric_for
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.filters import RANGE_CRITERIA, FilterKey
from faint_fuzzies.domain.findings import CatalogueError
from faint_fuzzies.storage import load_json_list

EVAL_DIR = Path("observations") / "owner" / "ai_eval"
CASES_FILE = EVAL_DIR / "rerank.json"
QUESTIONS_FILE = EVAL_DIR / "questions.json"
ORDERED = {*RANGE_CRITERIA, FilterKey.MAGNITUDE, FilterKey.MAGNITUDE_DELTA, FilterKey.SIZE}  # [min, max]


def read_cases(path: Path) -> list[dict[str, str]]:
    """The test cases of `path`.

    :raises CatalogueError: when the file is missing, not JSON, or a case lacks a search, a note or a valid
        expected verdict
    """
    if not path.is_file():
        raise CatalogueError(f"no test set at {path} (see faint_fuzzies.ai.evaluation)")
    cases = load_json_list(path, "test cases")
    for number, case in enumerate(cases, start=1):
        if not (isinstance(case, dict) and isinstance(case.get("search"), str) and isinstance(case.get("note"), str)
                and case.get("expected") in VERDICTS):
            raise CatalogueError(f"{path} case {number} needs a search, a note and an expected verdict of "
                                 f"{', '.join(VERDICTS)}")
    return cases


def evaluate(client: AiClient, model: str, cases: list[dict[str, str]],
             on_progress: Callable[[str, float], None] | None = None) -> dict[str, Any]:
    """Judges every case with `model` as reranking does - the rubric for each search (see rerank.rubric_for),
    then BATCH_SIZE notes of that search per request - and compares the verdicts with the expected ones.

    :returns: the report: the number of cases and of agreements, the share that agrees, the seconds the
        judging took (rubrics included), the rubric of each search, the confusion counts (expected -> got ->
        number; a verdict the model left out is "none"), and every case that disagrees
    :raises AiError: when the server fails
    """
    started = time.monotonic()
    rubrics: dict[str, dict[str, str]] = {}
    got = _judged(client, model, cases, rubrics, on_progress)
    confusion = {expected: {verdict: 0 for verdict in (*VERDICTS, "none")} for expected in VERDICTS}
    mismatches = []
    for case, verdict in zip(cases, got):
        confusion[case["expected"]][verdict or "none"] += 1
        if verdict != case["expected"]:
            mismatches.append({**case, "got": verdict})
    agree = len(cases) - len(mismatches)
    return {"model": model, "cases": len(cases), "agree": agree,
            "accuracy": round(agree / len(cases), 3) if cases else None,
            "seconds": round(time.monotonic() - started, 1), "rubrics": rubrics, "confusion": confusion,
            "mismatches": mismatches}


def _judged(client: AiClient, model: str, cases: list[dict[str, str]], rubrics: dict[str, dict[str, str]],
            on_progress: Callable[[str, float], None] | None) -> list[str | None]:
    """The model's verdict on each case, in the order of `cases`; the rubric of each search goes into
    `rubrics`."""
    by_search: dict[str, list[int]] = {}
    for number, case in enumerate(cases):
        by_search.setdefault(case["search"], []).append(number)
    batches = [(search, numbers[start:start + BATCH_SIZE]) for search, numbers in by_search.items()
               for start in range(0, len(numbers), BATCH_SIZE)]
    got: list[str | None] = [None] * len(cases)
    for done, (search, numbers) in enumerate(batches):
        if on_progress:
            on_progress(f"judging {len(cases)} test cases with {model}", done / len(batches))
        if search not in rubrics:
            rubrics[search] = rubric_for(client, model, search)
        notes = [cases[n]["note"] for n in numbers]
        for number, verdict in zip(numbers, judge_notes(client, model, search, notes, rubrics[search])):
            got[number] = verdict
    return got


def read_questions(path: Path) -> list[dict[str, Any]]:
    """The Questions of `path` (see the module docstring).

    :raises CatalogueError: when the file is missing, not JSON, or a case lacks a question, a filter object or
        a text (a string or null)
    """
    if not path.is_file():
        raise CatalogueError(f"no test set at {path} (see faint_fuzzies.ai.evaluation)")
    cases = load_json_list(path, "test questions")
    for number, case in enumerate(cases, start=1):
        if not (isinstance(case, dict) and isinstance(case.get("question"), str)
                and isinstance(case.get("filter"), dict) and "text" in case
                and (case["text"] is None or isinstance(case["text"], str))):
            raise CatalogueError(f"{path} question {number} needs a question, a filter and a text (or null)")
    return cases


def evaluate_questions(client: AiClient, model: str, cases: list[dict[str, Any]], context: Context,
                       on_progress: Callable[[str, float], None] | None = None) -> dict[str, Any]:
    """Asks every Question as `filter --question` does and compares the answer with the expected one.

    :returns: the report: the number of cases, of those whose filter and text agree, of those whose filter
        agrees and of those whose text does (there or not), the share that agrees in all, the seconds it took,
        and every case that disagrees, with what came out (or the error, for an answer that was rejected)
    :raises AiError: when the server fails
    :raises CatalogueError: when an expected filter names an object that is not there
    """
    started = time.monotonic()
    outcomes = []
    for number, case in enumerate(cases):
        if on_progress:
            on_progress(f"asking {len(cases)} test questions with {model}", number / len(cases))
        outcomes.append(_outcome(client, model, case, context))
    mismatches = [mismatch for _filter, _text, mismatch in outcomes if mismatch]
    agree = len(cases) - len(mismatches)
    return {"model": model, "cases": len(cases), "agree": agree,
            "filters_agree": sum(same_filter for same_filter, _text, _mismatch in outcomes),
            "texts_agree": sum(same_text for _filter, same_text, _mismatch in outcomes),
            "accuracy": round(agree / len(cases), 3) if cases else None,
            "seconds": round(time.monotonic() - started, 1), "mismatches": mismatches}


def _outcome(client: AiClient, model: str, case: dict[str, Any], context: Context) -> tuple[bool, bool, dict | None]:
    """Whether the answer to `case` has the expected filter and the expected text (there or not), and the case
    with what came out when either is not (or the error, for an answer that was rejected)."""
    expected = comparable(case["filter"], context.collection)
    try:
        answer = ask(client, model, case["question"], context)
    except QuestionError as exc:
        return False, False, {**case, "error": str(exc), "criteria": list(exc.criteria)}
    same_filter = comparable(answer.filter, context.collection) == expected
    same_text = (answer.text is None) == (case["text"] is None)
    if same_filter and same_text:
        return True, True, None
    return same_filter, same_text, {**case, "got": {"criteria": list(answer.criteria), "filter": answer.filter,
                                                    "text": answer.text, "ignored": list(answer.ignored)}}


def comparable(spec: dict[str, Any], collection: Collection) -> dict[str, Any]:
    """`spec` in a form that is equal for equal filters: every value a list, sorted unless it is a [min, max]
    range, its texts case-folded and its names replaced by the Objects they find.

    :raises CatalogueError: when a name is not there
    """
    result: dict[str, Any] = {}
    for key, value in spec.items():
        values = value if isinstance(value, list) else [value]
        if key == FilterKey.NAME_GROUP:  # the same Objects, however they are spelled ("M 13", "Messier 13")
            try:
                wanted = {name.casefold() for name in resolve_names(values, collection)}
            except QuestionError as exc:
                raise CatalogueError(f"test question names an unknown object: {exc}") from exc
            values = [index for index, obj in enumerate(collection.objects)
                      if any(name.casefold() in wanted for name in (*obj.names, *obj.groups))]
        if key in ORDERED:
            result[key] = [float(v) if isinstance(v, int | float) and not isinstance(v, bool) else v for v in values]
        else:
            result[key] = sorted((v.casefold() if isinstance(v, str) else v for v in values), key=repr)
    return result
