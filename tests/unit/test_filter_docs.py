"""Both the advanced filter's help text (ui/browse.py's `_ADVANCED_FILTER_HELP`, a curated subset) and README's
"Filter specification" tables are hand-written prose, with no mechanical tie to FilterKey - a rename or typo in either
would otherwise go unnoticed."""
import re
from pathlib import Path

from faint_fuzzies.domain.filters import FilterKey
from faint_fuzzies.ui.browse import _ADVANCED_FILTER_HELP

README = Path(__file__).parents[2] / "README.md"
_KEY = re.compile(r"`([a-z_]+)`")
_FILTER_SECTION = re.compile(r"^## Filter specification\n(.*?)(?=^#{1,2} )", re.DOTALL | re.MULTILINE)
_TABLE_ROW_KEY = re.compile(r"^\| `([a-z_]+)` \|", re.MULTILINE)


def test_every_documented_filter_key_is_a_real_filter_key():
    help_keys = {
        name
        for line in _ADVANCED_FILTER_HELP.splitlines()
        if line.startswith("- ") and " — " in line
        for name in _KEY.findall(line.split(" — ", 1)[0])
    }
    readme_keys = set(_TABLE_ROW_KEY.findall(_FILTER_SECTION.search(README.read_text(encoding="utf-8"))[1]))
    assert not sorted((help_keys | readme_keys) - {key.value for key in FilterKey})
