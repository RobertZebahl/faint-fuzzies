"""upload_site's on_line (upload.py): only the app's Site page passes it, never the "upload" command, so the Robot
upload tests never reach it."""
import sys

from faint_fuzzies import upload
from faint_fuzzies.config import UploadConfig


def test_with_on_line_rsyncs_output_is_relayed_line_by_line(tmp_path, monkeypatch):
    """The checks of the remote path, the tools and the password are stubbed, since the Robot upload tests cover
    them; rsync is replaced by a command that prints two lines."""
    monkeypatch.setattr(upload, "_check_remote_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(upload, "_check_tools_available", lambda: None)
    monkeypatch.setattr(upload, "_read_password", lambda user: "x")
    monkeypatch.setattr(upload, "_rsync_command",
                        lambda *args, **kwargs: [sys.executable, "-c", "print('first line'); print('second line')"])
    received = []
    config = UploadConfig(host="example.test", user="testuser", remote_path="/var/www/site")
    assert upload.upload_site(tmp_path, config, on_line=received.append) == 0
    assert received == ["first line", "second line"]
