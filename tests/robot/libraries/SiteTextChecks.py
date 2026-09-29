# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from faint_fuzzies.site.objects import build_description_text as _description_text


def build_description_text(record, locale, label=None):
    """The description of an observation as the site shows it (see site/objects.py)."""
    return _description_text(record, locale, label)
