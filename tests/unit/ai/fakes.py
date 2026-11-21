"""A stand-in for the model server: an embedding is the count of a few keywords in the text, plus one constant
dimension so no vector is zero - enough to tell which texts are about the same thing."""

KEYWORDS = ("kugelhaufen", "globular", "haufen", "nebel", "galax", "doppelstern", "text", "foto")


def keyword_vector(text, extra=()):
    lowered = text.lower()
    return [float(lowered.count(word)) for word in KEYWORDS] + [0.1] + list(extra)


class FakeClient:
    """Embeds with keyword_vector and remembers every text it was asked to embed.

    :ivar embedded: every text embedded, in order
    :ivar extra: dimensions appended to every vector, to play a model whose vectors have another length
    """

    def __init__(self, extra=()):
        self.embedded = []
        self.extra = tuple(extra)

    def embed(self, model, texts):
        self.embedded.extend(texts)
        return [keyword_vector(text, self.extra) for text in texts]
