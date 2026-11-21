"""Measuring the reranking against a test set: notes the user has judged by hand, so a change of prompt or model
shows in numbers rather than by comparing search results by eye.

::

    <data-dir>/observations/owner/ai_eval/rerank.json

A JSON list of cases, each {"search": ..., "note": ..., "expected": "yes" | "partly" | "no"} and optionally
"object" (only shown in the report). It holds observation texts, the user's own and the community's, so it lives
in the data directory, never in the repository.
"""
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.rerank import BATCH_SIZE, VERDICTS, judge_notes, rubric_for
from faint_fuzzies.domain.findings import CatalogueError
from faint_fuzzies.storage import load_json_list

CASES_FILE = Path("observations") / "owner" / "ai_eval" / "rerank.json"


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
