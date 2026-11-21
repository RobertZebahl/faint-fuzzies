"""Reranking a Description search with the chat model: it reads the best hits by embedding score and judges for
each whether its texts say that what was searched for was seen. That catches what embeddings miss - a negation
("no structure visible"), a word that only sounds alike ("visible with averted vision"), a search text that
asks for two things at once."""
import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.index import description_texts
from faint_fuzzies.ai.search import Hit, SearchResult
from faint_fuzzies.config import AiConfig

YES, PARTLY, NO = "yes", "partly", "no"
VERDICTS = (YES, PARTLY, NO)
CANDIDATES = 60   # the most notes judged per search
BATCH_SIZE = 10   # notes per request
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

KIND_INSTRUCTIONS = """Amateur astronomers search their observing notes. Say what kind of thing the search asks for, \
with one letter:
- "d": a detail seen inside a sky object - structure, spiral arms, a dust lane, dark lanes, knots, a bar, mottling.
- "c": colours - of a star, or of the components of a double or multiple star.
- "o": anything else."""

KIND_SCHEMA = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["d", "c", "o"]}},
    "required": ["kind"],
    "additionalProperties": False,
}

# The rubrics of the kinds of search the chat model is known to judge well with them, written by hand from the
# definitions in CONTEXT.md (Detail) and the user's rules for colours. A generated rubric (write_rubric) is only
# the fallback for any other kind: the model writes them unreliably.
RUBRICS = {
    "d": {
        "kind": "detail",
        "yes": "The note says the detail, or a more specific kind of it, was seen - a dust lane, a dark lane, a knot, "
               "a bar or a spiral arm is a structure. Seen with averted vision is still seen.",
        "partly": "The detail was seen only faintly or in traces (\"Ansätze\", \"ansatzweise\", \"erahnbar\", "
                  "\"teils\", \"hints of\"), however well the rest of the object was seen - unless the note also "
                  "says the detail was seen clearly (\"sicher\", \"deutlich\", \"clearly\"): that is \"y\".",
        "no": "Anything else: the detail is not mentioned, not seen, or only possibly seen (\"möglicherweise\", "
              "\"vielleicht\", \"nicht sicher\"). The object's overall shape, size or brightness, or a brighter "
              "centre, is not a detail, and being well seen (\"indirekt gut zu sehen\", \"sicher gesehen\") says "
              "nothing about one.",
        "examples": "(searching \"dust lane seen\") \"Dust lane obvious with averted vision.\" -> y; \"At 150x "
                    "traces of the dust lane.\" -> p; \"Bright and large, dust lane only partly visible.\" -> p; "
                    "\"Perhaps a dust lane, but I am not sure.\" -> n; \"Elongated, brighter core.\" -> n; \"Round, "
                    "but definitely and well seen with averted vision.\" -> n; \"Something faint flickered up now "
                    "and then.\" -> n.",
    },
    "c": {
        "kind": "colours",
        "yes": "The note names a colour of the stars or components - any colour, white too - or says they have the "
               "same or a similar colour, or no colour difference. A slight colour difference counts as well.",
        "partly": "The colour of only one component is named, while the other's could not be made out.",
        "no": "Anything else: no colour named, or the colours were not seen (\"Farben Fehlanzeige\", \"nicht "
              "erkennbar\"). A colour caused by the instrument (\"Farbfehler\", chromatic aberration, a coloured "
              "halo) or only implied by a brightness difference does not count. That components were seen, split, "
              "or equally or differently bright says nothing about colours.",
        "examples": "\"Each star looked white to me.\" -> y; \"Primary orange, companion bluish.\" -> y; \"The pair "
                    "shows hardly any difference in hue.\" -> y; \"Primary golden, the companion's tint escaped "
                    "me.\" -> p; \"Cleanly split, same brightness.\" -> n; \"Bluish fringes from the refractor's "
                    "chromatic aberration.\" -> n; \"All three stars clearly visible.\" -> n.",
    },
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

# The words a note must have to be judged for a search of the rubric's kind, written by hand like the rubric: the
# embedding ranks notes by what they share with the search text, the object rather than the Detail or the colour
# ("die Galaxie wirkt leicht unrund" for "Details oder Strukturen in der Galaxie gesehen": 11 of the 60 best notes
# named a Detail; "gleich hell" for "Farben der Komponenten erkannt": 34 of 60 named a colour). A word in a
# note that does not count ("Farbfehler", "ohne Farbunterschied") is for the judge to sort out.
CANDIDATE_WORDS = {
    "detail": re.compile(
        r"struktur|structur|detail|staub|dust|spiral|knoten|knötchen|\bknots?\b|balken|\bbarred\b|\bbar\b"
        r"|dunkelstruktur|dunkelwolke|dunkelband|\bdunkle\w* (?:band|bereich|fleck|zone|streifen|linie)"
        r"|\bdark (?:lanes?|bands?|patch\w*|structures?|zones?|rifts?|regions?|clouds?)"
        r"|einschnür|fleckig|gefleckt|mottl|patchy|clumpy|körnig|granul|inhomogen|ungleichmäßig|nicht homogen|uneven"
        r"|\w*band\b|\w*bänder|\blanes?\b|filament|\bh ?-?ii\b|sternwolke|star ?clouds?|absorption"
        r"|\barme?\b|\barmen\b|\barms?\b",
        re.IGNORECASE),
    "colours": re.compile(
        r"farb|färb|colou?r|\btint|\bhue\b"
        r"|gelb|orange|blau|bläu|grün|violett|purpur|türkis|kupfer|wärmer|kühl"
        r"|\b(?:\w*rot(?:e|er|es|en)?|rötlich\w*|\w*weiß\w*|\w*weiss\w*|gold\w*|\w*grau\w*|gräulich\w*|braun\w*|lila)\b"
        r"|\b(?:yellow\w*|red|reddish|ruddy|blue|bluish|white|whitish|green\w*|golden|copper\w*|purple|lilac|violet"
        r"|ash(?:en|y)|gr[ae]y\w*|warm\w*|cool\w*)\b",
        re.IGNORECASE),
}

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


def rubric_for(client: AiClient, model: str, query: str) -> dict[str, str]:
    """The rubric to judge `query`'s hits by: the hand-written one of its kind (see RUBRICS) when the chat model
    puts it in one, else one written for it (see write_rubric), with its "kind" set to "other".

    :raises AiError: when the server fails
    """
    answer = client.chat_json(model, [{"role": "system", "content": KIND_INSTRUCTIONS},
                                      {"role": "user", "content": f"Search: {query}"}], KIND_SCHEMA)
    kind = answer.get("kind") if isinstance(answer, dict) else None
    if kind in RUBRICS:
        return RUBRICS[kind]
    return {"kind": "other", **write_rubric(client, model, query)}


def rerank(client: AiClient, config: AiConfig, query: str, results: list[SearchResult],
           on_progress: Callable[[str, float], None] | None = None) -> Reranked:
    """The results with the best hits judged by the rubric for `query` (see rubric_for and _candidates): a hit
    judged "no", and one not judged, is dropped; an Object ranks by its best verdict ("yes" before "partly"),
    then by the best score among those hits.

    :param client: the model server
    :param config: the AI settings: its chat_model judges, and at most its limit of Objects are returned
    :param query: the search text
    :param results: the embedding search's results, with every hit above MIN_SCORE
    :param on_progress: told (step, fraction done) while the hits are judged
    :returns: the reranked results, best first, and the rubric
    :raises AiError: when the server fails
    """
    if on_progress:
        on_progress(f"choosing the rubric with {config.chat_model}", 0.0)
    rubric = rubric_for(client, config.chat_model, query)
    groups = list(_candidates(results, rubric).values())
    verdicts: dict[int, str] = {}
    for start in range(0, len(groups), BATCH_SIZE):
        if on_progress:
            on_progress(f"judging {len(groups)} notes with {config.chat_model}", start / len(groups))
        batch = groups[start:start + BATCH_SIZE]
        judged = judge_notes(client, config.chat_model, query, [_note(hits[0]) for hits in batch], rubric)
        verdicts.update((id(hit), verdict) for hits, verdict in zip(batch, judged) if verdict is not None
                        for hit in hits)
    reranked = []
    for result in results:
        hits = [replace(hit, verdict=verdicts[id(hit)]) for hit in result.hits
                if verdicts.get(id(hit)) in (YES, PARTLY)]
        if hits:
            hits.sort(key=lambda hit: (VERDICTS.index(hit.verdict or NO), -hit.score))
            reranked.append(SearchResult(result.match, tuple(hits)))
    reranked.sort(key=lambda result: (VERDICTS.index(result.verdict or NO), -result.score))
    return Reranked(reranked[:config.limit], rubric)


def _candidates(results: list[SearchResult], rubric: dict[str, str]) -> dict[str, list[Hit]]:
    """The hits worth judging, grouped by their note so each note is judged once: the hits of the CANDIDATES
    best-scoring notes, of only those notes with a word of CANDIDATE_WORDS when the rubric's kind has any.
    Notes are the same when their first text is (the same observation is often kept twice, once with and once
    without its English translation).

    :returns: the hits of each note, best first, the best note first
    """
    words = CANDIDATE_WORDS.get(rubric.get("kind", ""))
    groups: dict[str, list[Hit]] = {}
    for hit in sorted((hit for result in results for hit in result.hits), key=lambda hit: -hit.score):
        texts = description_texts(hit.found.observation)
        key = " ".join(texts[0].split()) if texts else ""
        if key in groups:
            groups[key].append(hit)
        elif len(groups) < CANDIDATES and (words is None or words.search(" ".join(texts))):
            groups[key] = [hit]
    return groups


def write_rubric(client: AiClient, model: str, query: str) -> dict[str, str]:
    """What counts as "yes", "partly" and "no" for `query`, written by the chat model from RUBRIC_GUIDANCE: one
    fixed set of judging rules cannot fit every search (structures in a galaxy, colours of a double star), and
    rules that do not fit the search confuse the model. Only used for a search of no kind in RUBRICS: the 8B
    models tried write rubrics unreliably (eval-ai: 64 instead of 69 of 73 for structures).

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
    :param rubric: what counts as each verdict for `query`, and maybe examples (see rubric_for)
    :returns: one verdict per note, in the order of `notes`
    :raises AiError: when the server fails
    """
    numbered = "\n".join(f"{number}. {note}" for number, note in enumerate(notes, start=1))
    rules = "\n".join(f"{letter}: {rubric.get(verdict, '')}" for letter, verdict in LETTERS.items())
    if rubric.get("examples"):
        rules += f"\nExamples: {rubric['examples']}"
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
