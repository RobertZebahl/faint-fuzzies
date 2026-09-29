# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""Direct check of upload_site's on_line streaming (faint_fuzzies.upload): used only by the app's Site page
(see ui/site.py), never by the "upload" CLI command, so upload.robot's subprocess-level tests never reach
it. The remote_path/tool/keyring checks it normally makes are stubbed out - they are already covered by
upload.robot - so this is purely about whether on_line receives rsync's lines as they are produced, in order,
rather than only at the end."""
import sys
import tempfile
from pathlib import Path

from faint_fuzzies import upload
from faint_fuzzies.config import UploadConfig


def upload_lines_received():
    """Runs upload_site with on_line set, its own remote_path/tool/keyring checks stubbed out and its rsync
    command replaced with one that simply prints two known lines; returns the lines on_line actually
    received, in order."""
    originals = (upload._check_remote_path, upload._check_tools_available,  # pylint: disable=protected-access
                upload._read_password, upload._rsync_command)  # pylint: disable=protected-access
    upload._check_remote_path = lambda *args, **kwargs: None  # pylint: disable=protected-access
    upload._check_tools_available = lambda: None  # pylint: disable=protected-access
    upload._read_password = lambda user: "x"  # pylint: disable=protected-access
    upload._rsync_command = (  # pylint: disable=protected-access
        lambda *args, **kwargs: [sys.executable, "-c", "print('first line'); print('second line')"])
    received = []
    try:
        config = UploadConfig(host="example.test", user="testuser", remote_path="/var/www/site")
        code = upload.upload_site(Path(tempfile.mkdtemp()), config, on_line=received.append)
    finally:
        (upload._check_remote_path, upload._check_tools_available,  # pylint: disable=protected-access
         upload._read_password, upload._rsync_command) = originals  # pylint: disable=protected-access
    return {"lines": received, "exit_code": code}
