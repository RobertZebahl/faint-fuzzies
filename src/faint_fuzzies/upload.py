"""Uploads a built website (see site/output.py, cli.py "build-site") to its host, over rsync run through ssh -
kept as its own command, not a build-site option, so a rebuild and an upload stay two independent,
individually-retriable steps: one never needs the network or the host's credentials, the other never needs the
data directory.

There is no SSH key for the host (see README): authentication is a password, read at run time from the OS
keyring (service "faint-fuzzies", username the config's upload user - see README, "keyring set faint-fuzzies
<user>") and handed to `sshpass -e`, which feeds it to ssh through the SSHPASS environment variable of the
rsync/ssh subprocess only - never on the command line (where `ps` could see it), never written by this tool to
config.toml or anywhere else on disk.

`-L` (--copy-links) makes rsync send the real file behind a symlink rather than the symlink itself: build-site's
default output links its images into the local data directory (see site/output.py) rather than copying them, and
a symlink to a path on this machine means nothing on the remote host, so this is not optional - it means the
plain build-site output can be uploaded directly, without needing --copy to duplicate every image locally first.
"""
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from faint_fuzzies.config import UploadConfig

KEYRING_SERVICE = "faint-fuzzies"


class UploadError(Exception):
    """The upload could not even be started: a required tool is missing, the target fails the safety check, or
    no password is stored for it. Never raised once rsync has actually begun transferring - its own exit code
    and its own output (streamed live, not captured - see upload_site) speak for what happened from there."""


def upload_site(output_dir: Path, config: UploadConfig, delete: bool = False, dry_run: bool = False,
                checksum: bool = False, on_line: Callable[[str], None] | None = None) -> int:
    """Uploads everything below `output_dir` to config.host:config.remote_path, as config.user, over rsync run
    through ssh, authenticated with the password stored in the keyring for config.user (see module docstring).
    With `delete`, the remote becomes an exact mirror of `output_dir` - refused (see _check_remote_path) when
    remote_path is empty or "/", the one guard against a config typo turning "upload --delete" into wiping the
    account's home or web root, unless config.confirm_delete_root says that is genuinely intended.
    config.exclude is passed through as one rsync --exclude per entry, always (not only with `delete`), so
    something the host itself writes into remote_path (a logs/ directory, say) is left alone by `delete` too,
    not just never overwritten.
    `dry_run` passes rsync -n: nothing is transferred or deleted, only reported.
    `checksum` passes rsync --checksum: a file is compared by its content instead of by its size and
    modification time, which is what decides it by default - slower (every file is read and hashed on both
    ends, not just the ones whose size or time changed), and rarely needed here, since the built site's own
    files are either freshly generated (so their time always changes) or untouched cache hits (whose time
    then never does) - see the README's "Uploading the website" for when it can matter (clock skew, or a
    file edited without its size changing).
    rsync's own output is never parsed, only relayed exactly as rsync writes it (its format is rsync's to
    define, not ours - see README): without `on_line`, straight to the terminal through this process's own
    stdout/stderr; given `on_line`, line by line to that callback instead, as rsync produces them - the way
    the app's Site page shows the upload live rather than only its final exit code.

    :param output_dir: the built website to upload (see site/output.py)
    :param config: the upload target and credentials lookup
    :param delete: whether the remote should become an exact mirror of `output_dir`
    :param dry_run: whether to pass rsync -n: nothing is transferred or deleted, only reported
    :param checksum: whether to pass rsync --checksum: compare files by content rather than size/time
    :param on_line: when given, receives each line of rsync's combined stdout/stderr as it is produced,
        instead of it going to this process's own terminal
    :returns: rsync's exit code, 0 for success
    :raises UploadError: before anything is sent: remote_path fails the safety check, `rsync` or `sshpass`
        is not on PATH, or the keyring has no password for config.user
    """
    _check_remote_path(config.remote_path, delete, config.confirm_delete_root)
    _check_tools_available()
    password = _read_password(config.user)
    command = _rsync_command(output_dir, config, delete=delete, dry_run=dry_run, checksum=checksum)
    env = {**os.environ, "SSHPASS": password}
    if on_line is None:
        return subprocess.run(command, env=env, check=False).returncode
    with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, bufsize=1) as process:
        assert process.stdout is not None  # guaranteed by stdout=PIPE above
        for line in process.stdout:
            on_line(line.rstrip("\n"))
        return process.wait()


def _check_remote_path(remote_path: str, delete: bool, confirm_delete_root: bool = False) -> None:
    """Refuses `delete` when `remote_path` is empty or "/" - the one guard against a config typo turning
    "upload --delete" into wiping the account's home or web root. Both spellings name the same danger: an
    empty `remote_path` is rsync's own "the account's default directory", and "/" means the server's true
    filesystem root unless the account is genuinely chrooted at the SSH/SFTP level (the OS remaps "/" to the
    webspace for that account specifically) - either way, "the whole account root", which is exactly as
    catastrophic to delete by accident regardless of which of the two a correctly-configured account happens
    to use for its real site root. `confirm_delete_root` lifts this refusal for whichever of the two
    `remote_path` actually is: the config says so once, deliberately, for this account's real site root.

    :param remote_path: the configured remote path
    :param delete: whether the upload will pass rsync --delete
    :param confirm_delete_root: whether `remote_path` being empty or "/" is confirmed intended, not a typo
    :raises UploadError: when `delete` is set and `remote_path` is empty or "/", unless `confirm_delete_root`
        is set
    """
    if delete and remote_path.rstrip("/") == "" and not confirm_delete_root:
        raise UploadError(f"refusing --delete: remote_path {remote_path!r} is empty or \"/\" - a config typo "
                          "here could otherwise delete the whole remote account (if this is genuinely your "
                          "site root, set confirm_delete_root = true in the [upload] table)")


def _read_password(user: str) -> str:
    """The password stored in the keyring for `user` (see module docstring).

    :param user: the upload user to look up
    :returns: the stored password
    :raises UploadError: when the keyring has none
    """
    import keyring  # optional dependency (the "upload" extra) - only needed for this one command
    password = keyring.get_password(KEYRING_SERVICE, user)
    if password is None:
        raise UploadError(f"no password stored for {user!r} in the keyring - "
                          f"set one first with: keyring set {KEYRING_SERVICE} {user}")
    return password


def _check_tools_available() -> None:
    """:raises UploadError: when `sshpass` or `rsync` is not on PATH"""
    if shutil.which("sshpass") is None:
        raise UploadError("sshpass not found - install it (it feeds the stored password to ssh non-interactively)")
    if shutil.which("rsync") is None:
        raise UploadError("rsync not found - install it")


def _rsync_command(output_dir: Path, config: UploadConfig, delete: bool, dry_run: bool, checksum: bool) -> list[str]:
    """Builds the sshpass/rsync command line for `upload_site`.

    :param output_dir: the built website to upload
    :param config: the upload target
    :param delete: whether to pass rsync --delete
    :param dry_run: whether to pass rsync -n
    :param checksum: whether to pass rsync --checksum
    :returns: the command, ready for subprocess.run
    """
    source = f"{output_dir}/"  # a trailing slash: copy the *contents* of output_dir, not output_dir itself
    destination = f"{config.user}@{config.host}:{config.remote_path}"
    command = ["sshpass", "-e", "rsync", "-avL", "-e", f"ssh -p {config.port}"]
    command += [f"--exclude={pattern}" for pattern in config.exclude]
    if delete:
        command.append("--delete")
    if dry_run:
        command.append("-n")
    if checksum:
        command.append("--checksum")
    command += [source, destination]
    return command
