import pytest

from tests.unit.builders import FIXTURES


@pytest.fixture
def fixtures_dir():
    """The fixture files shared with the Robot tests (see README's Tests section)."""
    return FIXTURES
