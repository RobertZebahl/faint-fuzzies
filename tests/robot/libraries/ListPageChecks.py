# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path
from types import SimpleNamespace

from faint_fuzzies.domain.lists import _order_text
from faint_fuzzies.domain.model import ObjectType
from faint_fuzzies.domain.sorting import natural_sort_key
from faint_fuzzies.site import menu
from faint_fuzzies.site.listpages import GLOBAL_PAGES, read_page_descriptions
from faint_fuzzies.site.listpages import describe as _describe

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _entry(*names, groups=()):
    return SimpleNamespace(unit=SimpleNamespace(names=tuple(names), groups=tuple(groups)))


def rows_in_page_order(page, *labels):
    """The first names of stand-in entries (`labels`, each name comma separated, a name starting with "group:"
    belongs to a Group without names) in the order the page of the list `page` shows them."""
    entries = []
    for label in labels:
        parts = label.split(",")
        if parts[0].startswith("group:"):
            entries.append(_entry(groups=[p.removeprefix("group:") for p in parts]))
        else:
            entries.append(_entry(*parts))
    key = GLOBAL_PAGES[page].sort_key
    return [(e.unit.names or e.unit.groups)[0] for e in sorted(entries, key=key)]


def pages_without_sort_key():
    return sorted(name for name, page in GLOBAL_PAGES.items() if page.sort_key is None)


def lists_of_the_menu_without_a_page():
    entries = [e for group in (menu.OBSERVATIONS, menu.BY_TYPE, menu.SPECIAL_GALAXIES, menu.SKETCHES)
               for e in group if isinstance(e, tuple) and e[0] is not None]
    return sorted(e[0] for e in entries if e[0] not in GLOBAL_PAGES)


def pages_with_description():
    """The pages fixtures/site/page_descriptions.json gives a description to, in either language."""
    page_descriptions, _why = read_page_descriptions(_FIXTURES)
    return sorted(name for name in GLOBAL_PAGES
                 if _describe(page_descriptions, name, "en") or _describe(page_descriptions, name, "de"))


def description(page, locale):
    page_descriptions, _why = read_page_descriptions(_FIXTURES)
    return _describe(page_descriptions, page, locale)


def title(page, locale):
    return GLOBAL_PAGES[page].title(locale)


def global_order(*specs):
    """The labels of stand-in objects ("name,name:type") in the order of the Global list."""
    objects = []
    for spec in specs:
        names, code = spec.rsplit(":", 1)
        names = tuple(names.split(","))
        objects.append(SimpleNamespace(names=names, label=names[0], types=(ObjectType.parse(code),)))
    return [o.label for o in sorted(objects, key=lambda o: natural_sort_key(_order_text(o)))]
