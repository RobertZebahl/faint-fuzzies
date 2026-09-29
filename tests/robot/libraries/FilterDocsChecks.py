# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
import re
from pathlib import Path

import faint_fuzzies
from faint_fuzzies.domain.filters import FilterKey
from faint_fuzzies.ui.browse import _ADVANCED_FILTER_HELP

_ROOT = Path(faint_fuzzies.__file__).resolve().parent.parent.parent
_KEY = re.compile(r"`([a-z_]+)`")
_FILTER_SECTION = re.compile(r"^## Filter specification\n(.*?)(?=^#{1,2} )", re.DOTALL | re.MULTILINE)
_TABLE_ROW_KEY = re.compile(r"^\| `([a-z_]+)` \|", re.MULTILINE)


def undocumented_filter_keys():
    """The bare key names mentioned in browse.py's `_ADVANCED_FILTER_HELP` or in README's "Filter
    specification" tables that are not a real, current FilterKey member - a rename or typo left in
    either doc, since neither is otherwise tied to the enum."""
    valid = {key.value for key in FilterKey}
    help_keys = {
        name
        for line in _ADVANCED_FILTER_HELP.splitlines()
        if line.startswith("- ") and " — " in line
        for name in _KEY.findall(line.split(" — ", 1)[0])
    }
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    section = _FILTER_SECTION.search(readme)
    readme_keys = set(_TABLE_ROW_KEY.findall(section[1]))
    return sorted((help_keys | readme_keys) - valid)
