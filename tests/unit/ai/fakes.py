"""A stand-in for the model server: an embedding is the count of a few keywords in the text, plus one constant
dimension so no vector is zero - enough to tell which texts are about the same thing. Its chat model judges a
note "n" (no) when it has a negation, "p" (partly) when it hedges, "y" (yes) when it has a word of the search,
and gives the notes listed in `skip` the unusable letter "x". Asked for the kind of a search, it gives `kind` ("o"
unless a test sets another); asked for a rubric, the same one for every search; asked a Question, `answer`, whose first step picks `criteria` (the keys of `answer`'s filter unless a test sets
others)."""
import re

NEGATIONS = ("nicht", "not", "keine", "kein")
HEDGES = ("möglicherweise", "possibly", "ansätze")

KEYWORDS = ("kugelhaufen", "globular", "haufen", "nebel", "galax", "doppelstern", "text", "foto")


def keyword_vector(text, extra=()):
    lowered = text.lower()
    return [float(lowered.count(word)) for word in KEYWORDS] + [0.1] + list(extra)


class FakeClient:
    """Embeds with keyword_vector and remembers every text it was asked to embed.

    :ivar embedded: every text embedded, in order
    :ivar extra: dimensions appended to every vector, to play a model whose vectors have another length
    """

    def __init__(self, extra=(), skip=()):
        self.embedded = []
        self.extra = tuple(extra)
        self.skip = set(skip)
        self.chats = []
        self.rubrics = []
        self.kinds = []
        self.kind = "o"
        self.answer = {"filter": {}, "text": None, "ignored": []}
        self.questions = []
        self.criteria = None
        self.choices = []

    def embed(self, model, texts):
        self.embedded.extend(texts)
        return [keyword_vector(text, self.extra) for text in texts]

    def chat_json(self, model, messages, schema, max_tokens=None):
        prompt = messages[-1]["content"]
        if "criteria" in schema.get("properties", {}):
            self.choices.append(messages)
            filter_ = self.answer.get("filter") if isinstance(self.answer, dict) else None
            return {"criteria": self.criteria if self.criteria is not None
                    else list(filter_) if isinstance(filter_, dict) else []}
        if "filter" in schema.get("properties", {}):
            self.questions.append(messages)
            return self.answer
        if "kind" in schema.get("properties", {}):
            self.kinds.append(prompt)
            return {"kind": self.kind}
        if "yes" in schema.get("properties", {}):
            self.rubrics.append(prompt)
            return {"yes": "it was seen.", "partly": "only traces.", "no": "anything else."}
        self.chats.append(prompt)
        search = prompt.split("\n", 1)[0].removeprefix("Search: ").lower()
        words = [word for word in re.findall(r"\w+", search) if len(word) > 3]
        verdicts = []
        for _number, note in re.findall(r"^(\d+)\. (.*)$", prompt, re.MULTILINE):
            lowered = note.lower()
            if note in self.skip:
                verdicts.append("x")
            elif set(re.findall(r"\w+", lowered)) & set(NEGATIONS):
                verdicts.append("n")
            elif any(word in lowered for word in HEDGES):
                verdicts.append("p")
            else:
                verdicts.append("y" if any(word in lowered for word in words) else "n")
        return {"verdicts": verdicts}
