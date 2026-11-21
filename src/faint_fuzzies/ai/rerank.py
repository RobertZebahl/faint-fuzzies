"""Reranking a Description search with the chat model: it reads the best hits by embedding score and judges for
each whether its texts say that what was searched for was seen. That catches what embeddings miss - a negation
("no structure visible"), a word that only sounds alike ("visible with averted vision"), a search text that
asks for two things at once."""
from collections.abc import Callable
from dataclasses import replace

from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.index import description_texts
from faint_fuzzies.ai.search import Hit, SearchResult
from faint_fuzzies.config import AiConfig

YES, PARTLY, NO = "yes", "partly", "no"
VERDICTS = (YES, PARTLY, NO)
CANDIDATES = 60   # the most hits judged per search
BATCH_SIZE = 10   # hits per request
MIN_SCORE = 0.55  # the embedding pre-filter: below it, a text is not worth asking about
TEXT_LENGTH = 600

INSTRUCTIONS = """You judge notes that amateur astronomers wrote about what they saw of a sky object, in German or \
English. The search names a detail or property they may have seen. For every numbered note, decide whether the \
note says that this detail - or a clear synonym of it - was seen:
- "yes": the note clearly says it was seen.
- "partly": only hinted at, uncertain ("possibly", "Ansätze", "ansatzweise", "erahnbar"), or only part of it.
- "no": the note does not mention it, or says it was not seen.
That the object itself was seen, or its shape, size or brightness, is not enough: answer "no" unless the search \
asks for exactly that. Judge only what the note says, not what would be expected of such an object. Give one \
verdict for every number."""

SCHEMA = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object",
        "properties": {"number": {"type": "integer"}, "verdict": {"type": "string", "enum": list(VERDICTS)}},
        "required": ["number", "verdict"], "additionalProperties": False}}},
    "required": ["verdicts"],
    "additionalProperties": False,
}


def rerank(client: AiClient, config: AiConfig, query: str, results: list[SearchResult],
           on_progress: Callable[[str, float], None] | None = None) -> list[SearchResult]:
    """The results with the CANDIDATES best hits judged: a hit judged "no", and one not judged, is dropped;
    an Object ranks by its best verdict ("yes" before "partly"), then by the best score among those hits.

    :param client: the model server
    :param config: the AI settings: its chat_model judges, and at most its limit of Objects are returned
    :param query: the search text
    :param results: the embedding search's results, with every hit above MIN_SCORE
    :param on_progress: told (step, fraction done) while the hits are judged
    :returns: the reranked results, best first
    :raises AiError: when the server fails
    """
    candidates = sorted((hit for result in results for hit in result.hits), key=lambda hit: -hit.score)
    candidates = candidates[:CANDIDATES]
    verdicts: dict[int, str] = {}
    for start in range(0, len(candidates), BATCH_SIZE):
        if on_progress:
            on_progress(f"judging {len(candidates)} hits with {config.chat_model}", start / len(candidates))
        batch = candidates[start:start + BATCH_SIZE]
        for number, verdict in _judge(client, config.chat_model, query, batch).items():
            verdicts[id(batch[number - 1])] = verdict
    reranked = []
    for result in results:
        hits = [replace(hit, verdict=verdicts[id(hit)]) for hit in result.hits
                if verdicts.get(id(hit)) in (YES, PARTLY)]
        if hits:
            hits.sort(key=lambda hit: (VERDICTS.index(hit.verdict or NO), -hit.score))
            reranked.append(SearchResult(result.match, tuple(hits)))
    reranked.sort(key=lambda result: (VERDICTS.index(result.verdict or NO), -result.score))
    return reranked[:config.limit]


def _judge(client: AiClient, model: str, query: str, hits: list[Hit]) -> dict[int, str]:
    """The verdict on each hit, by its 1-based number in `hits`; a number the model left out has none."""
    notes = "\n".join(f"{number}. {_note(hit)}" for number, hit in enumerate(hits, start=1))
    answer = client.chat_json(model, [{"role": "system", "content": INSTRUCTIONS},
                                      {"role": "user", "content": f"Search: {query}\n\nNotes:\n{notes}"}], SCHEMA)
    verdicts: dict[int, str] = {}
    for item in answer.get("verdicts", []) if isinstance(answer, dict) else []:
        number, verdict = item.get("number"), item.get("verdict")
        if isinstance(number, int) and 1 <= number <= len(hits) and isinstance(verdict, str) and verdict in VERDICTS:
            verdicts.setdefault(number, verdict)
    return verdicts


def _note(hit: Hit) -> str:
    """The texts of the hit's observation in one line (a German and an English one are the same note)."""
    text = " / ".join(description_texts(hit.found.observation))
    text = " ".join(text.split())
    return text if len(text) <= TEXT_LENGTH else text[:TEXT_LENGTH] + "…"
