"""The local AI features: Description search now, Questions later. Everything here talks to a model server the
user runs (see docs/adr/0001-local-ai-via-external-server-outside-filterspec.md) and needs the `ai` extra;
nothing in the domain depends on it."""


class AiError(Exception):
    """The model server could not be reached, or gave an answer that cannot be used."""
