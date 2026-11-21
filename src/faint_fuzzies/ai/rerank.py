"""Reranking a Description search with the chat model: it reads the best hits by embedding score and judges for
each whether its texts say that what was searched for was seen. That catches what embeddings miss - a negation
("no structure visible"), a word that only sounds alike ("visible with averted vision"), a search text that
asks for two things at once."""
from collections.abc import Callable
from dataclasses import dataclass, replace

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

RUBRIC_GUIDANCE = """You write a rubric for judging notes that amateur astronomers wrote, in German or English, about \
what they saw of a sky object. The search says what to look for. Write one short English sentence (at most 40 \
words) for each verdict:
- "yes": what a note must say for it to have been seen.
- "partly": what makes it seen only in traces, or only part of it.
- "no": everything else - name the things that sound related but do not count.
Make the rubric specific to this search: name the words and kinds of things that count, and those that do not.
Follow these rules wherever they fit the search:
- A more specific kind of what is searched for counts: a dust lane, a dark lane, a knot, a bar or a spiral arm is a \
structure; orange, blue or white are colours.
- For a detail inside an object (structure, spiral arms, dust lane, ...): the object's overall shape, size or \
brightness, or a brighter centre, is not a detail.
- For colours (of a star, of a double star's components): any named colour counts, white too, and so does saying \
the components have the same or a similar colour, or no colour difference; a slight colour difference counts. Only \
one component's colour named is "partly". A colour caused by the instrument (chromatic aberration, "Farbfehler", a \
coloured halo) or only implied by a brightness difference does not count, and neither does saying that the \
components were seen, split or equally bright.
- Traces ("Ansätze", "ansatzweise", "erahnbar", "teils", "hints of") are "partly".
- Doubt that it was seen ("möglicherweise", "vielleicht", "nicht sicher", "possibly") is "no"."""

RUBRIC_SCHEMA = {
    "type": "object",
    "properties": {verdict: {"type": "string"} for verdict in VERDICTS},
    "required": list(VERDICTS),
    "additionalProperties": False,
}

INSTRUCTIONS = """You judge notes that amateur astronomers wrote about what they saw of a sky object, in German or \
English. For every numbered note, decide by the rubric whether the note says that what the search asks for was \
seen: "y" (yes), "p" (partly) or "n" (no).
Whatever the search:
- Only what the note says about what the search asks for counts. How well the object was seen says nothing about \
it: "indirekt gut zu sehen", "sicher gesehen", "well seen with averted vision" alone are "n".
- Averted vision ("indirekt", "bei indirektem Sehen") is a normal observing technique, not a doubt.
- Doubt about whether the object itself was seen ("blitzte etwas auf", "not seen for sure") is "n".
- Judge only what the note says, not what would be expected of such an object.
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


@dataclass(frozen=True)
class Reranked:
    """The outcome of reranking.

    :ivar results: the reranked results, best first
    :ivar rubric: the rubric the hits were judged by
    """
    results: list[SearchResult]
    rubric: dict[str, str]


def rerank(client: AiClient, config: AiConfig, query: str, results: list[SearchResult],
           on_progress: Callable[[str, float], None] | None = None) -> Reranked:
    """The results with the CANDIDATES best hits judged by a rubric written for `query` (see write_rubric): a
    hit judged "no", and one not judged, is dropped; an Object ranks by its best verdict ("yes" before
    "partly"), then by the best score among those hits.

    :param client: the model server
    :param config: the AI settings: its chat_model judges, and at most its limit of Objects are returned
    :param query: the search text
    :param results: the embedding search's results, with every hit above MIN_SCORE
    :param on_progress: told (step, fraction done) while the hits are judged
    :returns: the reranked results, best first, and the rubric
    :raises AiError: when the server fails
    """
    candidates = sorted((hit for result in results for hit in result.hits), key=lambda hit: -hit.score)
    candidates = candidates[:CANDIDATES]
    if on_progress:
        on_progress(f"writing the rubric with {config.chat_model}", 0.0)
    rubric = write_rubric(client, config.chat_model, query)
    verdicts: dict[int, str] = {}
    for start in range(0, len(candidates), BATCH_SIZE):
        if on_progress:
            on_progress(f"judging {len(candidates)} hits with {config.chat_model}", start / len(candidates))
        batch = candidates[start:start + BATCH_SIZE]
        judged = judge_notes(client, config.chat_model, query, [_note(hit) for hit in batch], rubric)
        verdicts.update((id(hit), verdict) for hit, verdict in zip(batch, judged) if verdict is not None)
    reranked = []
    for result in results:
        hits = [replace(hit, verdict=verdicts[id(hit)]) for hit in result.hits
                if verdicts.get(id(hit)) in (YES, PARTLY)]
        if hits:
            hits.sort(key=lambda hit: (VERDICTS.index(hit.verdict or NO), -hit.score))
            reranked.append(SearchResult(result.match, tuple(hits)))
    reranked.sort(key=lambda result: (VERDICTS.index(result.verdict or NO), -result.score))
    return Reranked(reranked[:config.limit], rubric)


def write_rubric(client: AiClient, model: str, query: str) -> dict[str, str]:
    """What counts as "yes", "partly" and "no" for `query`, written by the chat model from RUBRIC_GUIDANCE: one
    fixed set of judging rules cannot fit every search (structures in a galaxy, colours of a double star), and
    rules that do not fit the search confuse the model.

    :param client: the model server
    :param model: the chat model
    :param query: the search text
    :returns: one sentence for each verdict; empty for one the model gave none for
    :raises AiError: when the server fails
    """
    answer = client.chat_json(model, [{"role": "system", "content": RUBRIC_GUIDANCE},
                                      {"role": "user", "content": f"Search: {query}"}], RUBRIC_SCHEMA)
    answer = answer if isinstance(answer, dict) else {}
    return {verdict: " ".join(str(answer.get(verdict) or "").split()) for verdict in VERDICTS}


def judge_notes(client: AiClient, model: str, query: str, notes: list[str],
                rubric: dict[str, str]) -> list[str | None]:
    """The chat model's verdict on each note (one request), None for a note it gave no usable letter for.

    :param client: the model server
    :param model: the chat model
    :param query: the search text
    :param notes: the notes, one line each
    :param rubric: what counts as each verdict for `query` (see write_rubric)
    :returns: one verdict per note, in the order of `notes`
    :raises AiError: when the server fails
    """
    numbered = "\n".join(f"{number}. {note}" for number, note in enumerate(notes, start=1))
    rules = "\n".join(f"{letter}: {rubric.get(verdict, '')}" for letter, verdict in LETTERS.items())
    answer = client.chat_json(model, [{"role": "system", "content": INSTRUCTIONS},
                                      {"role": "user", "content": f"Search: {query}\n\nRubric:\n{rules}\n\n"
                                                                  f"Notes:\n{numbered}"}],
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
