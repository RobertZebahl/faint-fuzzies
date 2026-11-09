from pathlib import Path

import pytest

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def fixtures_dir():
    """The fixture files shared with the Robot tests (see README's Tests section)."""
    return FIXTURES
