"""Reading and writing data files: a JSON list loaded with one consistent set of error messages, and a
write that never leaves a half-written file behind after a failed or interrupted save."""
import json
import os
import shutil
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import CatalogueError


def load_json_list(path: Path, noun: str) -> list[Any]:
    """Reads `path` and parses it as a JSON list.

    :param path: the file to load
    :param noun: what the list holds, for the "does not contain a JSON list of ..." message
    :returns: the parsed list, in file order
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file cannot be read, is not valid
        UTF-8 or JSON, or is not a JSON list
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogueError(f"cannot read {path}: {exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise CatalogueError(f"{path} is not valid UTF-8: {exc.reason}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc
    if not isinstance(data, list):
        raise CatalogueError(f"{path} does not contain a JSON list of {noun}")
    return data


def write_text_atomically(path: Path, text: str) -> None:
    """Replaces the file in one step, so an interrupted save never leaves half a file behind.

    :param path: the file to write
    :param text: the file's new contents
    :raises OSError: when the file cannot be written
    """
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(text.encode("utf-8"))
        if path.exists():
            shutil.copymode(path, temporary)
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
