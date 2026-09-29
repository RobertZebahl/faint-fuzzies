# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from types import SimpleNamespace

from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.site.objects import get_display_names as _get_display_names
from faint_fuzzies.site.projects import _names as _entry_names


def get_display_names(value, locale=None):
    """The display names of a NAME or GROUP value (see site/objects.py)."""
    return _get_display_names(value, locale)


def group_display_names(group_value, locale=None):
    """The names the Double Stars project page shows for a Group unit whose own GROUP value is `group_value`
    (see site/projects.py's _names)."""
    unit = SimpleNamespace(is_group=True, record={ObjectAttribute.GROUP: group_value})
    return _entry_names(SimpleNamespace(unit=unit), locale)
