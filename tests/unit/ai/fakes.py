"""A stand-in for the model server: an embedding is the count of a few keywords in the text, plus one constant
dimension so no vector is zero - enough to tell which texts are about the same thing. Its chat model judges a
note "no" when it has a negation, "partly" when it hedges, "yes" when it has a word of the search, and leaves
out the notes listed in `skip`."""
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

    def embed(self, model, texts):
        self.embedded.extend(texts)
        return [keyword_vector(text, self.extra) for text in texts]

    def chat_json(self, model, messages, schema):
        prompt = messages[-1]["content"]
        self.chats.append(prompt)
        search = prompt.split("\n", 1)[0].removeprefix("Search: ").lower()
        words = [word for word in re.findall(r"\w+", search) if len(word) > 3]
        verdicts = []
        for number, note in re.findall(r"^(\d+)\. (.*)$", prompt, re.MULTILINE):
            lowered = note.lower()
            if note in self.skip:
                continue
            if set(re.findall(r"\w+", lowered)) & set(NEGATIONS):
                verdict = "no"
            elif any(word in lowered for word in HEDGES):
                verdict = "partly"
            else:
                verdict = "yes" if any(word in lowered for word in words) else "no"
            verdicts.append({"number": int(number), "verdict": verdict})
        return {"verdicts": verdicts}
