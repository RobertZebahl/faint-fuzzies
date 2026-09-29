# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from faint_fuzzies.site.objects import build_description_text as _description_text
from faint_fuzzies.site.objects import local_conditions_items as _local_conditions_items


def build_description_text(record, locale, label=None):
    """The description of an observation as the site shows it (see site/objects.py) - the local conditions
    near the object are not here any more, see Local Conditions Items."""
    return _description_text(record, locale, label)


def local_conditions_items(record):
    """The local conditions near the object, as HEAD-like items (see site/objects.py's
    local_conditions_items) - its content (the "NELM"/"FST" word, the "Local conditions near the object"
    label) is looked up by the template itself, not tested here."""
    return _local_conditions_items(record)
