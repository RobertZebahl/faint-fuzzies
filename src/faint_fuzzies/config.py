"""The user's config file, so day-to-day commands (currently "serve", "upload") do not need the same options
every time, and the settings of the local AI server ("filter --search")."""
import tomllib
from dataclasses import dataclass
from pathlib import Path

from faint_fuzzies.domain.findings import CatalogueError

CONFIG_PATH = Path.home() / ".config" / "faint-fuzzies" / "config.toml"


def resolve_data_dir(explicit: Path | None) -> Path:
    """The data directory: --data-dir if given, otherwise "data_dir" from the config file.

    :param explicit: the --data-dir value, if the command line gave one
    :returns: the resolved data directory
    :raises faint_fuzzies.domain.findings.CatalogueError: when `explicit` is None and the config file is
        missing or has no usable 'data_dir' entry
    """
    if explicit is not None:
        return explicit
    if not CONFIG_PATH.is_file():
        raise CatalogueError(f"no --data-dir given and no config file at {CONFIG_PATH} "
                             f"(it needs a 'data_dir' entry, for example: data_dir = \"/path/to/data\")")
    data = _read_config()
    value = data.get("data_dir")
    if not isinstance(value, str):
        raise CatalogueError(f"{CONFIG_PATH} needs a 'data_dir' string entry")
    return Path(value).expanduser()


@dataclass(frozen=True)
class UploadConfig:
    """The "upload" table of the config file.

    :ivar host: the SSH host to upload to
    :ivar user: the SSH user
    :ivar remote_path: the remote path the site is uploaded into
    :ivar port: the SSH port, 22 (the standard SSH port) by default
    :ivar confirm_delete_root: whether `remote_path = "/"` is genuinely intended (an SSH account whose own
        root already is the site root, rather than a config typo) - see upload.py's `_check_remote_path`
    :ivar exclude: rsync exclude patterns (relative to `remote_path`) for things that live alongside the site
        on the host but are not part of it - a `logs/` directory the host writes to, say - so `--delete`
        never touches them
    """
    host: str
    user: str
    remote_path: str
    port: int = 22
    confirm_delete_root: bool = False
    exclude: tuple[str, ...] = ()


def resolve_upload_config() -> UploadConfig:
    """The "upload" table of the config file: host, user and remote_path (required strings), and port (an
    optional integer, default 22 - the standard SSH port). There is no --host/--user/... equivalent on the
    command line: unlike the data directory, an upload target is a fixed fact about the host, not something
    to point at a different value per run.

    :returns: the resolved upload config
    :raises faint_fuzzies.domain.findings.CatalogueError: when the config file is missing, or its [upload]
        table is missing or invalid
    """
    if not CONFIG_PATH.is_file():
        raise CatalogueError(f"no config file at {CONFIG_PATH} (it needs an [upload] table - see the README)")
    data = _read_config()
    upload = data.get("upload")
    if not isinstance(upload, dict):
        raise CatalogueError(f"{CONFIG_PATH} needs an [upload] table with host, user and remote_path entries")
    missing = [key for key in ("host", "user", "remote_path") if not isinstance(upload.get(key), str)]
    if missing:
        raise CatalogueError(f"{CONFIG_PATH}'s [upload] table needs string entries for: {', '.join(missing)}")
    port = upload.get("port", 22)
    if not isinstance(port, int) or isinstance(port, bool):
        raise CatalogueError(f"{CONFIG_PATH}'s [upload].port must be an integer")
    confirm_delete_root = upload.get("confirm_delete_root", False)
    if not isinstance(confirm_delete_root, bool):
        raise CatalogueError(f"{CONFIG_PATH}'s [upload].confirm_delete_root must be true or false")
    exclude = upload.get("exclude", [])
    if not isinstance(exclude, list) or not all(isinstance(item, str) for item in exclude):
        raise CatalogueError(f"{CONFIG_PATH}'s [upload].exclude must be a list of strings")
    return UploadConfig(host=upload["host"], user=upload["user"], remote_path=upload["remote_path"], port=port,
                        confirm_delete_root=confirm_delete_root, exclude=tuple(exclude))


@dataclass(frozen=True)
class AiConfig:
    """The "ai" table of the config file: the local model server that Questions and Description search use
    (see docs/adr/0001-local-ai-via-external-server-outside-filterspec.md).

    :ivar url: the base URL of the server's OpenAI-compatible API, for example "http://localhost:11434/v1"
    :ivar chat_model: the language model that turns a Question into a filter
    :ivar embedding_model: the model that turns Descriptions into vectors; a multilingual one, so a German
        and an English text about the same thing land close together
    :ivar min_score: the lowest similarity (cosine, -1 to 1) a Description search still counts as a hit
    :ivar limit: the most Observations a Description search returns
    :ivar timeout: seconds to wait for one answer of the server
    """
    url: str
    chat_model: str
    embedding_model: str
    min_score: float = 0.5
    limit: int = 100
    timeout: float = 300.0


def read_ai_config() -> AiConfig | None:
    """The "ai" table of the config file, or None when there is no config file or it has no such table - the
    AI features are then simply not there.

    :returns: the resolved AI config, or None
    :raises faint_fuzzies.domain.findings.CatalogueError: when the [ai] table is there but invalid
    """
    if not CONFIG_PATH.is_file():
        return None
    ai = _read_config().get("ai")
    if ai is None:
        return None
    if not isinstance(ai, dict):
        raise CatalogueError(f"{CONFIG_PATH}'s 'ai' entry must be a table ([ai])")
    missing = [key for key in ("url", "chat_model", "embedding_model") if not isinstance(ai.get(key), str)]
    if missing:
        raise CatalogueError(f"{CONFIG_PATH}'s [ai] table needs string entries for: {', '.join(missing)}")
    min_score = float(_ai_number(ai, "min_score", AiConfig.min_score, whole=False))
    limit = int(_ai_number(ai, "limit", AiConfig.limit, whole=True))
    timeout = float(_ai_number(ai, "timeout", AiConfig.timeout, whole=False))
    if not -1.0 <= min_score <= 1.0:
        raise CatalogueError(f"{CONFIG_PATH}'s [ai].min_score must be between -1 and 1")
    if limit < 1 or timeout <= 0:
        raise CatalogueError(f"{CONFIG_PATH}'s [ai].limit and [ai].timeout must be greater than 0")
    return AiConfig(url=ai["url"].rstrip("/"), chat_model=ai["chat_model"], embedding_model=ai["embedding_model"],
                    min_score=min_score, limit=limit, timeout=timeout)


def _ai_number(ai: dict, key: str, default: float, whole: bool) -> float:
    """An optional number of the [ai] table, `default` when it is not there.

    :raises faint_fuzzies.domain.findings.CatalogueError: when it is not a number (a whole one, with `whole`)
    """
    value = ai.get(key, default)
    if not isinstance(value, int if whole else (int, float)) or isinstance(value, bool):
        raise CatalogueError(f"{CONFIG_PATH}'s [ai].{key} must be a {'whole ' if whole else ''}number")
    return value


def _read_config() -> dict:
    """The parsed config file.

    :returns: the config file's top-level TOML table
    :raises faint_fuzzies.domain.findings.CatalogueError: when the file is not valid TOML
    """
    try:
        return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CatalogueError(f"invalid TOML in {CONFIG_PATH}: {exc}") from exc
