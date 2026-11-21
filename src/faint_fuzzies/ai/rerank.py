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
English. The search names a detail they may have seen inside the object. For every numbered note, decide whether \
the note says that this detail was seen - a more specific kind of it counts too (a dust lane, a dark lane, a knot \
or a spiral arm is a structure):
- "y": the detail was seen.
- "p": the detail was seen, but only faintly or in traces ("Ansätze", "ansatzweise", "erahnbar", "teils", "hints of").
- "n": anything else - the note does not mention the detail, says it was not seen, or doubts that it was seen at \
all ("möglicherweise", "vielleicht", "nicht sicher", "possibly", "not sure").
Rules:
- Averted vision ("indirekt", "bei indirektem Sehen", "averted vision") is a normal observing technique, not a \
doubt: a detail seen with averted vision is "y".
- The object's overall shape, size or brightness, or a brighter centre, is not a detail: a note that only \
describes those is "n".
- Doubt about whether the object itself was seen ("blitzte etwas auf", "not seen for sure") is not a hint of a \
detail: "n".
- Judge only what the note says, not what would be expected of such an object.
Examples for the search "dust lane seen": "Dust lane obvious with averted vision." -> y; "At 150x traces of the \
dust lane." -> p; "Perhaps a dust lane, but I am not sure." -> n; "Elongated, brighter core." -> n; "Something \
faint flickered up now and then." -> n.
Answer with one letter per note, in the order of the numbers."""

# one letter per verdict keeps the answer short: generating it is most of the time a judgement takes
LETTERS = {"y": YES, "p": PARTLY, "n": NO}


def schema(count: int) -> dict:
    """The answer to a request with `count` notes: exactly one letter for each, in order."""
    return {
        "type": "object",
        "properties": {"verdicts": {"type": "array", "items": {"type": "string", "enum": list(LETTERS)},
                                    "minItems": count, "maxItems": count}},
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
    """The verdict on each hit, by its 1-based number in `hits`; one the model gave no usable letter for has
    none."""
    verdicts = judge_notes(client, model, query, [_note(hit) for hit in hits])
    return {number: verdict for number, verdict in enumerate(verdicts, start=1) if verdict is not None}


def judge_notes(client: AiClient, model: str, query: str, notes: list[str]) -> list[str | None]:
    """The chat model's verdict on each note (one request), None for a note it gave no usable letter for.

    :param client: the model server
    :param model: the chat model
    :param query: the search text
    :param notes: the notes, one line each
    :returns: one verdict per note, in the order of `notes`
    :raises AiError: when the server fails
    """
    numbered = "\n".join(f"{number}. {note}" for number, note in enumerate(notes, start=1))
    answer = client.chat_json(model, [{"role": "system", "content": INSTRUCTIONS},
                                      {"role": "user", "content": f"Search: {query}\n\nNotes:\n{numbered}"}],
                              schema(len(notes)))
    letters = answer.get("verdicts") if isinstance(answer, dict) else None
    if not isinstance(letters, list):
        return [None] * len(notes)
    letters = (letters + [None] * len(notes))[:len(notes)]
    return [LETTERS.get(letter) if isinstance(letter, str) else None for letter in letters]


def _note(hit: Hit) -> str:
    """The texts of the hit's observation in one line (a German and an English one are the same note)."""
    text = " / ".join(description_texts(hit.found.observation))
    text = " ".join(text.split())
    return text if len(text) <= TEXT_LENGTH else text[:TEXT_LENGTH] + "…"
