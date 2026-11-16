"""The pages of the Website lists: which lists have one and how their rows are ordered (by the catalogue number, the
Herschel number). Their title and description are content, not structure - they come from
site/static/php/page_content.php, not tested here."""
from types import SimpleNamespace

from faint_fuzzies.domain.lists import _order_text
from faint_fuzzies.domain.model import ObjectType
from faint_fuzzies.domain.sorting import natural_sort_key
from faint_fuzzies.site import menu
from faint_fuzzies.site.listpages import GLOBAL_PAGES


def _entry(*names, groups=()):
    return SimpleNamespace(unit=SimpleNamespace(names=tuple(names), groups=tuple(groups)))


def _rows_in_page_order(page, *entries):
    return [(e.unit.names or e.unit.groups)[0] for e in sorted(entries, key=GLOBAL_PAGES[page].sort_key)]


def test_every_list_of_the_menu_has_a_page_except_the_gallery_and_the_remarks():
    """The gallery is a page of its own, not a list of rows; the remarks entry is a page of text (see build.py's
    STATIC_PAGES), not a Website list either."""
    entries = [e for group in (menu.OBSERVATIONS, menu.BY_TYPE, menu.SPECIAL_GALAXIES, menu.SKETCHES)
               for e in group if isinstance(e, tuple) and e[0] is not None]
    assert sorted(e[0] for e in entries if e[0] not in GLOBAL_PAGES) == ["remarks", "sketches-gallery"]


def test_catalogue_numbers_are_ordered_as_numbers():
    rows = _rows_in_page_order("berkeley-clusters", _entry("Berkeley 10"), _entry("Berkeley 9"), _entry("Berkeley 100"),
                               _entry("Berkeley 1"))
    assert rows == ["Berkeley 1", "Berkeley 9", "Berkeley 10", "Berkeley 100"]


def test_the_last_name_with_a_number_decides():
    """Joined names are matched greedily, so the last "Messier n" counts."""
    rows = _rows_in_page_order("messier", _entry("IC4703", "Messier 16"), _entry("NGC224", "Messier 31"),
                               _entry("Messier 1", "Messier 2"))
    assert rows == ["Messier 1", "IC4703", "NGC224"]


def test_a_group_without_names_is_ordered_by_its_group_names():
    rows = _rows_in_page_order("hickson-groups", _entry("Hickson 44"), _entry(groups=["Hickson 7"]),
                               _entry("Hickson 100"))
    assert rows == ["Hickson 7", "Hickson 44", "Hickson 100"]


def test_herschel_numbers_are_ordered_part_by_part():
    """H2.5 before H2.14 before H2.14.1 before H10.1; an object without a Herschel name comes first."""
    rows = _rows_in_page_order("herschel-2500", _entry("NGC3", "H10.1"), _entry("NGC2", "H2.14.1"),
                               _entry("NGC1", "H2.14"), _entry("NGC0", "H2.5"), _entry("NGC9"))
    assert rows == ["NGC9", "NGC0", "NGC1", "NGC2", "NGC3"]


def test_the_other_lists_keep_the_order_of_the_global_list():
    assert sorted(name for name, page in GLOBAL_PAGES.items() if page.sort_key is None) == sorted([
        "asterisms", "bright-nebulae", "complete-object-list", "dark-nebulae", "double-stars", "galaxies-and-groups",
        "galaxies-in-messier-44", "globular-clusters", "local-group", "open-clusters", "planetary-nebulae",
        "red-stars", "ring-galaxies", "sketches-comets", "sketches-deepsky", "sketches-moon", "sketches-planets",
        "sketches-sun", "superthin-galaxies", "thin-galaxies"])


def test_the_solar_system_comes_first_in_the_global_list():
    """The Moon, the Sun, the planets in the order of the sky, asteroids, comets; then everything else."""
    specs = [(("NGC1",), "GC"), (("Comet2",), "C"), (("Jupiter",), "P"), (("Ceres",), "A"), (("Mars",), "P"),
             (("Mond", "Moon"), "S"), (("Sonne", "Sun"), "S"), (("15 Aql",), "**"), (("Comet1",), "C")]
    objects = [SimpleNamespace(names=names, label=names[0], types=(ObjectType.parse(code),)) for names, code in specs]
    found = [o.label for o in sorted(objects, key=lambda o: natural_sort_key(_order_text(o)))]
    assert found == ["Mond", "Sonne", "Mars", "Jupiter", "Ceres", "Comet1", "Comet2", "15 Aql", "NGC1"]
