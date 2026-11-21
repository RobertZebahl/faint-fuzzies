"""Questions: a request in natural language, German or English, turned by the chat model into a FilterSpec and,
optionally, the text of a Description search (see docs/adr/0001-local-ai-via-external-server-outside-filterspec.md).
It takes two requests: the model first picks which of the criteria that make sense in a Question it names, then
fills in a JSON schema of only those - offered every criterion at once, an 8B model added some never asked for
(has_sketch, a date up to today), and made to answer each one it filled them all in. What no criterion can
express it lists as ignored. Object names it passes on as written, and the tool finds them among the real names;
the answer is checked like any filter, and one that is not valid is rejected, never guessed at."""
import difflib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from faint_fuzzies.ai import AiAnswerError, AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.filters import FilterKey, FilterSpec, FilterSpecError
from faint_fuzzies.domain.formats import CONSTELLATIONS
from faint_fuzzies.domain.lists import LISTS
from faint_fuzzies.domain.model import ObjectType
from faint_fuzzies.domain.names import compact_key, full_key, name_forms
from faint_fuzzies.domain.observation import Difficulty, Method, OpticType
from faint_fuzzies.domain.observer import Observers, Scope
from faint_fuzzies.domain.seen import SeenStatus

K = FilterKey
MAX_TOKENS = 800  # an answer is rarely 100 tokens: more is one that does not end
CHOICE_TOKENS = 200

# The criteria a Question can use (the others stay with --filter: they are about the data's upkeep, or regular
# expressions, or rarely asked for), each with what the model is told about it.
CRITERIA: dict[FilterKey, str] = {
    K.TYPE: "object types: galaxy, double star, open or globular cluster, nebula, ...",
    K.CONSTELLATION: "IAU constellation abbreviations, e.g. \"UMa\" for Großer Bär / Ursa Major",
    K.MAGNITUDE: "[min, max] magnitude; brighter is smaller: \"brighter than 10\" is [null, 10]",
    K.MAGNITUDE_DELTA: "[min, max] magnitude difference of a double star's two components",
    K.SEPARATION: "[min, max] separation of a double star in arcseconds",
    K.SIZE: "[min, max] size in arcminutes (the smaller diameter)",
    K.SIZE_RATIO: "[min, max] major over minor diameter: elongation",
    K.SEEN: "the object's status: \"seen\", \"failed\" (only failed attempts), \"not_observed\"",
    K.PROJECT: "objects on that list",
    K.CATALOGUE: "objects of that catalogue file",
    K.NAME_GROUP: "object names exactly as the question writes them (\"M 31\", \"NGC 891\", \"Albireo\")",
    K.OBSERVER: "observations by these observers (ids below)",
    K.SCOPE: "observations by observers of this role: OWNER is the user (\"my\", \"meine\", \"ich\"), GLOBAL, "
             "PROJECT",
    K.METHOD: "observations made \"visual\" or \"photographic\"",
    K.OPTIC_TYPE: "observations with \"naked_eye\", \"binoculars\" or \"telescope\"",
    K.APERTURE: "[min, max] aperture in mm of the instrument used; 1 inch = 25.4 mm, rounded: 4 inch = 102",
    K.DATE: "[min, max] dates \"YYYY-MM-DD\" the observation was made",
    K.HAS_SKETCH: "observations with (true) or without (false) a sketch",
    K.HAS_PHOTOGRAPH: "observations with (true) or without (false) a photograph",
    K.HAS_IMAGE: "observations with (true) or without (false) a sketch or photograph",
    K.PUBLIC_GRADE: "how the object went, on a public observation (see Grades)",
    K.PRIVATE_GRADE: "[min, max] grade of a private observation (see Grades)",
}
RANGES = {K.MAGNITUDE, K.MAGNITUDE_DELTA, K.SEPARATION, K.SIZE, K.SIZE_RATIO, K.APERTURE, K.PRIVATE_GRADE}
FLAGS = {K.HAS_SKETCH, K.HAS_PHOTOGRAPH, K.HAS_IMAGE}
PUBLIC_GRADES = tuple(member.value for member in Difficulty)

TYPE_NAMES = {
    "P": "planet", "C": "comet", "A": "asteroid", "S": "Sun or Moon", "*": "star", "**": "double or multiple star",
    "V*": "variable star", "C*": "carbon star", "Ast": "asterism", "OC": "open cluster", "GC": "globular cluster",
    "PN": "planetary nebula", "BN": "bright nebula", "EN": "emission nebula", "RN": "reflection nebula",
    "DN": "dark nebula", "Gx": "galaxy", "GxG": "galaxy group", "GxC": "galaxy cluster", "Q": "quasar",
    "EG": "other extragalactic object", "N": "nova", "SN": "supernova", "NE": "non-existent object",
}

INSTRUCTIONS = """You turn a question an amateur astronomer asks about their observing records, in German or \
English, into a filter and a search text. Answer with JSON:
- "filter": a value for each of the criteria below, as the question gives it.
- "text": what the observation notes must say, for a question about what was seen or noticed ("Details", \
"Farben", "spiral arms seen"), in the question's language and without the filter's part; null when the \
question asks for nothing in the notes.
- "ignored": every part of the question that none of the criteria can express (a month or season, "bright" \
without a number, a property not listed), in the question's words; empty when nothing is left over.
Do not guess numbers the question does not give, except by these conventions:
- thin galaxy: size_ratio [5, null]; superthin: size_ratio [7, null].
- small telescope: aperture [null, 102].
- binoculars, Fernglas: optic_type ["binoculars"].
Grades: a public observation states a public_grade, a private one a private_grade; never use both. Use \
public_grade, unless the question asks for private or personal observations ("privat", "persönlich", \
"private", "personal"): then private_grade. A double star has no public_grade.
- public_grade: EASY (easy, clearly visible), MEDIUM (needed averted vision), HARD (barely, with averted \
vision), FAILED (not seen).
- private_grade of a double star: 1 separated, 2 not separated but elongated, 3 failed.
- private_grade of a deep sky object (galaxy, nebula, unresolved cluster): 1 very easy, 2 clearly visible \
with direct vision, 3 barely visible with direct vision, 4 needed averted vision, 5 barely perceptible with \
averted vision, 6 failed.
- private_grade of a resolvable open cluster: 1 showpiece, 2 conspicuous, 3 clearly visible, 4 barely stands \
out, 5 very inconspicuous, 6 failed.
A range is [min, max], null leaving a side open. Today is {today}: "last year", "since 2020" become date \
ranges.

Criteria:
{criteria}

Object types: {types}

Lists (project): {projects}

Catalogues: {catalogues}

Observers (id: name): {observers}

Examples:
{examples}"""

CHOICE_INSTRUCTIONS = """You read a question an amateur astronomer asks about their observing records, in German \
or English, and name the filter criteria it asks for, from the list below. Name only those the question states; \
most questions name one to three, and many words name none (they are about what was seen in the notes, or about \
nothing a criterion can express). Answer with JSON: {{"criteria": [...]}}.
- "my", "meine", "ich" (the user's own observations): scope.
- thin or superthin galaxies: size_ratio. A small telescope, inches, millimetres: aperture. Binoculars, \
Fernglas, naked eye: optic_type.
- How the object went (easy, averted vision, failed): public_grade; private_grade only when the question asks \
for private or personal observations ("privat", "persönlich", "private", "personal").
- A year, a date, "since", "last year": date. A season or month alone is no criterion.

Criteria:
{criteria}

Examples:
{examples}"""

EXAMPLES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("Welche Galaxien zeigten Details mit bis zu 4 Zoll Öffnung?",
     {"filter": {"type": ["Gx"], "aperture": [None, 102]}, "text": "Details gesehen", "ignored": []}),
    ("Double stars in Cygnus closer than 3 arcseconds that I split",
     {"filter": {"type": ["**"], "constellation": ["Cyg"], "separation": [None, 3], "scope": ["OWNER"]},
      "text": "components split", "ignored": []}),
    ("Meine privaten Beobachtungen von M 31 mit dem Fernglas, nur indirekt gesehen",
     {"filter": {"name_group": ["M 31"], "scope": ["OWNER"], "optic_type": ["binoculars"],
                 "private_grade": [4, 5]}, "text": None, "ignored": []}),
    ("Helle Kugelsternhaufen, im Winter beobachtet, mit Skizze",
     {"filter": {"type": ["GC"], "has_sketch": True}, "text": None, "ignored": ["Helle", "im Winter"]}),
)


class QuestionError(AiError):
    """The chat model's answer to a Question cannot be used: its filter is not valid, or it names an object that
    is not there."""


@dataclass(frozen=True)
class Context:
    """What a Question is asked against.

    :ivar collection: the loaded collection, for its catalogues and the real object names
    :ivar observers: the observers, if there are any
    :ivar today: the date relative dates are counted from
    """
    collection: Collection
    observers: Observers | None
    today: date


@dataclass(frozen=True)
class Answer:
    """What a Question asks for.

    :ivar filter: the FilterSpec, in its JSON form, its object names those of the data
    :ivar text: the text of the Description search, None when the Question asks for none
    :ivar ignored: the parts of the Question no criterion could express, in its own words
    :ivar criteria: the criteria the model picked in its first step (see choose_criteria)
    """
    filter: dict[str, Any]
    text: str | None
    ignored: tuple[str, ...]
    criteria: tuple[str, ...] = ()


def ask(client: AiClient, model: str, question: str, context: Context) -> Answer:
    """The FilterSpec and search text `question` stands for (see the module docstring).

    :param client: the model server
    :param model: the chat model
    :param question: the Question
    :param context: what it is asked against
    :returns: the answer, its filter a valid FilterSpec
    :raises AiError: when the server fails (QuestionError: when the model's filter is not valid, or a name is
        not found)
    """
    catalogues = [catalogue.name for catalogue in context.collection.catalogues]
    known = sorted(context.observers or (), key=lambda o: o.id)
    chosen = choose_criteria(client, model, question)
    criteria = "\n".join(f"- {key}: {CRITERIA[key]}" for key in chosen) or "none: the filter stays empty"
    prompt = INSTRUCTIONS.format(
        today=context.today.isoformat(), criteria=criteria,
        types=", ".join(f"{code} {name}" for code, name in TYPE_NAMES.items()),
        projects=", ".join(LISTS), catalogues=", ".join(catalogues) or "none",
        observers=", ".join(f"{o.id}: {o.firstname} {o.surname}" for o in known) or "none",
        examples="\n".join(f"Question: {q}\nAnswer: {json.dumps(a, ensure_ascii=False)}" for q, a in EXAMPLES))
    try:
        raw = client.chat_json(model, [{"role": "system", "content": prompt},
                                       {"role": "user", "content": f"Question: {question}"}],
                               schema(catalogues, [o.id for o in known], chosen), MAX_TOKENS)
    except AiAnswerError as exc:
        raise QuestionError(str(exc)) from exc
    answer = answer_of(raw, context.collection)
    return Answer(answer.filter, answer.text, answer.ignored, tuple(str(key) for key in chosen))


def choose_criteria(client: AiClient, model: str, question: str) -> tuple[FilterKey, ...]:
    """The criteria `question` names, picked by the chat model from CRITERIA (the first of a Question's two
    requests, see the module docstring); one it names twice counts once.

    :raises AiError: when the server fails (QuestionError: when the answer is not JSON)
    """
    prompt = CHOICE_INSTRUCTIONS.format(
        criteria="\n".join(f"- {key}: {about}" for key, about in CRITERIA.items()),
        examples="\n".join(f"Question: {q}\nAnswer: {json.dumps({'criteria': list(a['filter'])})}"
                           for q, a in EXAMPLES))
    choice_schema = {"type": "object",
                     "properties": {"criteria": {"type": "array", "items": {"type": "string",
                                                                            "enum": [str(k) for k in CRITERIA]}}},
                     "required": ["criteria"], "additionalProperties": False}
    try:
        raw = client.chat_json(model, [{"role": "system", "content": prompt},
                                       {"role": "user", "content": f"Question: {question}"}],
                               choice_schema, CHOICE_TOKENS)
    except AiAnswerError as exc:
        raise QuestionError(str(exc)) from exc
    picked = raw.get("criteria") if isinstance(raw, dict) else None
    names = {str(key): key for key in CRITERIA}
    return tuple(dict.fromkeys(names[item] for item in picked if isinstance(item, str) and item in names)) \
        if isinstance(picked, list) else ()


def answer_of(raw: Any, collection: Collection) -> Answer:
    """The model's answer `raw` made usable: empty criteria dropped, names replaced by the data's, and the
    filter checked.

    :raises QuestionError: when the filter is not valid or a name is not found
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("filter"), dict):
        raise QuestionError(f"the chat model gave no filter: {json.dumps(raw, ensure_ascii=False)[:300]}")
    spec = {key: value for key, value in raw["filter"].items() if not _empty(value)}
    if unknown := sorted(spec.keys() - set(CRITERIA)):  # a server that ignores the schema
        raise QuestionError(f"the chat model's filter uses '{unknown[0]}', which a Question cannot")
    if K.NAME_GROUP in spec:
        spec[K.NAME_GROUP] = resolve_names(spec[K.NAME_GROUP] if isinstance(spec[K.NAME_GROUP], list)
                                           else [spec[K.NAME_GROUP]], collection)
    try:
        FilterSpec.from_dict(spec)
    except FilterSpecError as exc:
        raise QuestionError(f"the chat model's filter is not valid ({exc}): {json.dumps(spec, ensure_ascii=False)}") \
            from exc
    text = raw.get("text")
    text = " ".join(text.split()) if isinstance(text, str) else ""
    ignored = raw.get("ignored")
    ignored = tuple(item.strip() for item in ignored if isinstance(item, str) and item.strip()) \
        if isinstance(ignored, list) else ()
    return Answer(spec, text or None, ignored)


def resolve_names(names: Iterable[Any], collection: Collection) -> list[str]:
    """The data's spellings of `names`: a name is found whatever its case, with or without its first space
    ("M 31", "m31"), and by its short form as object_name_abbreviations.json gives it ("Messier 31" -> "M31").

    :raises QuestionError: when a name is not found, with the closest names there are
    """
    by_key: dict[str, set[str]] = {}
    for obj in collection.objects:
        for name in (*obj.names, *obj.groups):
            by_key.setdefault(compact_key(full_key(name)), set()).add(name)
    resolved: list[str] = []
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        found = {real for form in name_forms(" ".join(name.split())) for real in
                 by_key.get(compact_key(full_key(form)), ())}
        if not found:
            close = difflib.get_close_matches(compact_key(full_key(name)), by_key, n=3, cutoff=0.8)
            hint = f"; did you mean {', '.join(sorted(min(by_key[key]) for key in close))}?" if close else ""
            raise QuestionError(f"no object is named '{name}'{hint}")
        resolved.extend(sorted(found - set(resolved)))
    return resolved


def schema(catalogues: list[str], observer_ids: list[str], keys: Iterable[FilterKey] = tuple(CRITERIA)) -> dict[
        str, Any]:
    """The JSON schema of the answer: a value for each of `keys` (the criteria picked, see choose_criteria) and
    no other criterion, its values restricted to the known ones."""
    def choices(values: Iterable[str]) -> dict[str, Any]:
        return {"type": "array", "items": {"type": "string", "enum": list(values)}}

    number = {"type": ["number", "null"]}
    day = {"type": ["string", "null"], "pattern": r"^\d{4}-\d{2}-\d{2}$"}
    properties: dict[str, Any] = {
        K.TYPE: choices(t.value for t in ObjectType),
        K.CONSTELLATION: choices(CONSTELLATIONS.values()),
        K.SEEN: choices(s.value for s in SeenStatus),
        K.PROJECT: choices(LISTS),
        K.CATALOGUE: choices(catalogues),
        K.NAME_GROUP: {"type": "array", "items": {"type": "string"}},
        K.OBSERVER: choices(observer_ids),
        K.SCOPE: choices(s.value for s in Scope),
        K.METHOD: choices(m.value for m in Method),
        K.OPTIC_TYPE: choices(o.value for o in OpticType),
        K.DATE: {"type": "array", "items": day, "minItems": 2, "maxItems": 2},
        K.PUBLIC_GRADE: choices(PUBLIC_GRADES),
        **{key: {"type": "array", "items": number, "minItems": 2, "maxItems": 2} for key in RANGES},
        **{key: {"type": "boolean"} for key in FLAGS},
    }
    if not catalogues:
        del properties[K.CATALOGUE]
    if not observer_ids:
        del properties[K.OBSERVER]
    wanted = [key for key in keys if key in properties]
    return {
        "type": "object",
        "properties": {
            "filter": {"type": "object", "properties": {str(key): properties[key] for key in wanted},
                       "required": [str(key) for key in wanted], "additionalProperties": False},
            "text": {"type": ["string", "null"]},
            "ignored": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["filter", "text", "ignored"],
        "additionalProperties": False,
    }


def _empty(value: Any) -> bool:
    """Whether a criterion's value asks for nothing: null, an empty list, or a range open on both sides."""
    return value is None or value == [] or value == "" or (isinstance(value, list) and len(value) == 2
                                                            and all(bound is None for bound in value))
