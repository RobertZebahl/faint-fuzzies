"""Description search: ranking the Observations of a filter's matches by how well their Descriptions fit a
search text. It is a layer on top of the filter, never a FilterSpec criterion (see
docs/adr/0001-local-ai-via-external-server-outside-filterspec.md)."""
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.ai.index import DescriptionIndex, description_texts, normalized
from faint_fuzzies.domain.filters import Match
from faint_fuzzies.domain.observation import FoundObservation


@dataclass(frozen=True)
class Hit:
    """An Observation that fits the search text.

    :ivar found: the observation and the Object that holds it
    :ivar score: the cosine similarity of its best text to the search text
    :ivar verdict: the chat model's judgement (see faint_fuzzies.ai.rerank), None when not reranked
    """
    found: FoundObservation
    score: float
    verdict: str | None = None


@dataclass(frozen=True)
class SearchResult:
    """A matched Object with at least one hit.

    :ivar match: the filter's Match, with all of its observations
    :ivar hits: its observations that are hits, best first
    """
    match: Match
    hits: tuple[Hit, ...]

    @property
    def score(self) -> float:
        return self.hits[0].score

    @property
    def verdict(self) -> str | None:
        return self.hits[0].verdict


def query_vector(client: AiClient, model: str, text: str) -> np.ndarray:
    return normalized(np.asarray(client.embed(model, [text]), dtype=np.float32))[0]


def rank(matches: Sequence[Match], query: np.ndarray, index: DescriptionIndex, min_score: float,
         limit: int) -> list[SearchResult]:
    """The matches with hits, the best first. A hit is an Observation whose best text scores at least
    `min_score`; an Object ranks by its best hit, and at most `limit` Objects are kept, each with all of its
    hits - so an Object observed many times cannot crowd the others out.

    :param matches: the filter's matches
    :param query: the search text's normalized vector
    :param index: the Descriptions' vectors
    :param min_score: the lowest cosine similarity that is still a hit
    :param limit: the most Objects returned
    :returns: the matches that have a hit, best first
    """
    if not index.rows:
        return []
    scores = index.vectors @ query
    results = []
    for match in matches:
        hits = []
        for found in match.observations:
            rows = [row for text in description_texts(found.observation)
                    if (row := index.row_of(text)) is not None]
            if rows and (best := float(scores[rows].max())) >= min_score:
                hits.append(Hit(found, best))
        if hits:
            hits.sort(key=lambda hit: -hit.score)
            results.append(SearchResult(match, tuple(hits)))
    results.sort(key=lambda result: -result.score)  # stable: equal scores keep the filter's order
    return results[:limit]
