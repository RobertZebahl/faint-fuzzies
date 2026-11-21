"""The embedding index of the Descriptions: one vector per distinct text, cached in the data directory so only
new or changed texts go to the model server.

::

    <data-dir>/cache/ai/embeddings-<model>.npz    the texts' SHA-256 hashes and their vectors, one file per
                                                  embedding model

A vector only depends on its text and on the model, so a text is keyed by its hash and the file by the model:
switching models starts a file of its own and keeps the old one, and an edited Description is simply a new
text. Texts no Observation has any more are dropped whenever the index is updated. Deleting the folder is
always safe; it is rebuilt on the next search.
"""
import hashlib
import os
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from faint_fuzzies.ai import AiError
from faint_fuzzies.ai.client import AiClient
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.observation import Observation

CACHE_DIR = Path("cache") / "ai"
BATCH_SIZE = 32
# write the file every so many batches, so an interrupted first build (minutes) keeps what it has done
SAVE_EVERY = 20

ProgressCallback = Callable[[str, float], None]


def description_texts(observation: Observation) -> tuple[str, ...]:
    """The texts a Description search looks at: the Observation's Descriptions in every language and the
    Notes of a Community observation, each distinct text once.

    :param observation: the observation
    :returns: its searchable texts, possibly none
    """
    texts = [text for _language, text in observation.descriptions]
    if notes := observation.notes.strip():
        texts.append(notes)
    return tuple(dict.fromkeys(texts))


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(vectors: np.ndarray) -> np.ndarray:
    """The rows of `vectors` scaled to length 1 (a zero row stays zero), so a dot product is the cosine."""
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(lengths == 0, 1, lengths)


@dataclass(frozen=True)
class DescriptionIndex:
    """The vectors of the Descriptions, normalized.

    :ivar rows: a text's key (see text_key) -> its row in `vectors`
    :ivar vectors: one row per text
    """
    rows: dict[str, int]
    vectors: np.ndarray

    def row_of(self, text: str) -> int | None:
        return self.rows.get(text_key(text))


def index_path(root: Path, model: str) -> Path:
    return root / CACHE_DIR / f"embeddings-{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.npz"


def update_index(root: Path, objects: Iterable[Object], client: AiClient, model: str,
                 on_progress: ProgressCallback | None = None) -> DescriptionIndex:
    """The index of every Description of `objects`, embedding only the texts the cached file does not have yet,
    and writing the file back when anything changed.

    :param root: the data directory
    :param objects: the Objects whose Observations (own and community) are indexed
    :param client: the model server
    :param model: the embedding model
    :param on_progress: told (step, fraction done) while texts are embedded
    :returns: the index
    :raises AiError: when the server fails
    """
    wanted = _wanted_texts(objects)
    path = index_path(root, model)
    cached = _read(path, model)
    missing = [key for key in wanted if key not in cached]
    vectors: dict[str, np.ndarray] = {}
    if missing and cached:
        # one text first: vectors of another length mean the model behind the name changed, so nothing
        # cached fits any more
        first = missing.pop(0)
        vectors[first] = normalized(np.asarray(client.embed(model, [wanted[first]]), dtype=np.float32))[0]
        if vectors[first].shape[0] != next(iter(cached.values())).shape[0]:
            cached = {}
            missing = [key for key in wanted if key != first]
    vectors.update({key: cached[key] for key in wanted if key in cached})
    for number, embedded in enumerate(_embedded_batches(client, model, {key: wanted[key] for key in missing},
                                                        on_progress), start=1):
        vectors.update(embedded)
        if number % SAVE_EVERY == 0:
            _write(path, model, vectors)
    if vectors.keys() != cached.keys():
        _write(path, model, vectors)
    keys = list(vectors)
    return DescriptionIndex({key: row for row, key in enumerate(keys)}, _matrix(vectors))


def _wanted_texts(objects: Iterable[Object]) -> dict[str, str]:
    """Every searchable text of the Observations of `objects`, by key."""
    wanted: dict[str, str] = {}
    for obj in objects:
        for observation in obj.all_observations:
            for text in description_texts(observation):
                wanted.setdefault(text_key(text), text)
    return wanted


def _embedded_batches(client: AiClient, model: str, missing: dict[str, str],
                      on_progress: ProgressCallback | None) -> Iterator[dict[str, np.ndarray]]:
    """The normalized vectors of the `missing` texts (by key), BATCH_SIZE of them at a time."""
    keys = list(missing)
    for start in range(0, len(keys), BATCH_SIZE):
        if on_progress:
            on_progress(f"embedding {len(keys)} new description texts", start / len(keys))
        batch = keys[start:start + BATCH_SIZE]
        embedded = normalized(np.asarray(client.embed(model, [missing[key] for key in batch]), dtype=np.float32))
        yield dict(zip(batch, embedded))


def _matrix(vectors: dict[str, np.ndarray]) -> np.ndarray:
    return np.stack(list(vectors.values())) if vectors else np.zeros((0, 0), dtype=np.float32)


def _read(path: Path, model: str) -> dict[str, np.ndarray]:
    """The cached vectors by key; empty when there is no usable file (it is then rebuilt, never an error)."""
    try:
        with np.load(path, allow_pickle=False) as data:
            if str(data["model"]) != model:
                return {}
            keys: list[str] = np.asarray(data["keys"]).tolist()
            return dict(zip(keys, data["vectors"]))
    except (OSError, KeyError, ValueError):
        return {}


def _write(path: Path, model: str, vectors: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(vectors)
    matrix = _matrix(vectors)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("wb") as file:
            np.savez(file, model=np.array(model), keys=np.array(keys, dtype="U64"), vectors=matrix)
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise AiError(f"cannot write the description index {path}: {exc.strerror}") from exc
