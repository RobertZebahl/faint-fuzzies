"""A keyring backend for tests only, selected via the PYTHON_KEYRING_BACKEND environment variable (keyring's
own documented mechanism - see keyring.core.load_env) so upload.py's real, unmodified `import keyring;
keyring.get_password(...)` call can be exercised end to end without a real OS secret store. Returns
FAKE_KEYRING_PASSWORD for the service "faint-fuzzies" (any username), or None if that variable is not set -
so a test can choose whether "a password is stored" simply by setting or leaving out that one variable."""
import os

from keyring.backend import KeyringBackend


class FakeKeyring(KeyringBackend):
    priority = 1  # only ever picked when PYTHON_KEYRING_BACKEND names it explicitly; irrelevant otherwise

    def get_password(self, service, username):
        return os.environ.get("FAKE_KEYRING_PASSWORD") if service == "faint-fuzzies" else None

    def set_password(self, service, username, password):
        raise NotImplementedError("tests only ever read a password, never store one through this backend")

    def delete_password(self, service, username):
        raise NotImplementedError("tests only ever read a password, never delete one through this backend")
