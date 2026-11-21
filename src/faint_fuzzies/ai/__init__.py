"""The local AI features: Description search now, Questions later. Everything here talks to a model server the
user runs (see docs/adr/0001-local-ai-via-external-server-outside-filterspec.md) and needs the `ai` extra;
nothing in the domain depends on it."""


class AiError(Exception):
    """The model server could not be reached, or gave an answer that cannot be used."""


class AiHttpError(AiError):
    """The model server answered with an error status.

    :ivar status: the HTTP status code
    :ivar detail: the start of the server's message
    """

    def __init__(self, message: str, status: int, detail: str):
        super().__init__(message)
        self.status = status
        self.detail = detail


class AiAnswerError(AiError):
    """The chat model's answer is not the JSON that was asked for - cut off at its token limit, say."""
