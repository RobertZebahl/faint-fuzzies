# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from faint_fuzzies.domain.observation import Observation


def descriptions_of(record):
    """The (language, text) pairs the info panel shows for an observation with this record."""
    return [list(pair) for pair in Observation(record, public=True, optic=None, visibility=()).descriptions]
