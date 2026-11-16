"""The lists behind the website's menu, defined on the Global list (domain/lists.py). The menu shows a count beside
each list, so a list is defined here even when its page is not built yet. Fixture "website_lists": an own catalogue
of small cases and a Herschel catalogue."""
import pytest

from faint_fuzzies.domain.lists import LISTS, WEBSITE_SUBLISTS, build_list, website_count
from tests.unit.builders import FIXTURES, load_catalogues

WORLD = FIXTURES / "website_lists"


@pytest.fixture(scope="module")
def lists():
    """{list name: (the sorted first names of its entries, the number the menu shows for it)}."""
    collection, references = load_catalogues(WORLD / "own.json", WORLD / "herschel.json")
    entries = build_list(LISTS["global"], collection, references).entries
    return {name: (sorted((e.unit.names or e.unit.groups)[0] for e in entries if name in e.sublists),
                   website_count(name, entries))
            for name in WEBSITE_SUBLISTS}


def _cases(*rows):
    return [pytest.param(name, list(expected), id=name) for name, *expected in rows]


@pytest.mark.parametrize(("name", "expected"), _cases(
    ("berkeley-clusters", "Berkeley 1"),
    ("king-clusters", "King 5"),
    ("abell-planetary-nebulae", "Abell 21"),
    ("ring-galaxies", "NGC2685"),
    ("messier", "Messier 16", "Messier 31"),
))
def test_name_and_type_rules(lists, name, expected):
    """"Berkeley 2b" is not "Berkeley" and a number: names are matched whole."""
    assert lists[name][0] == expected


@pytest.mark.parametrize(("name", "expected"), _cases(
    ("local-group", "NGC224"),
    ("hickson-groups", "Hickson 1"),
    ("arp-galaxies", "Arp10", "Arp20"),
))
def test_groups_and_local_group(lists, name, expected):
    """The Local Group is a GROUP of the galaxies; Hickson and Arp groups are group records."""
    assert lists[name][0] == expected


@pytest.mark.parametrize(("name", "expected"), _cases(
    ("thin-galaxies", "NGC1", "NGC2"),
    ("superthin-galaxies", "NGC2"),
))
def test_thin_galaxies_are_judged_by_the_ratio_of_the_two_diameters(lists, name, expected):
    """5:1 is thin, 7:1 is also superthin; a zero minor diameter or a missing one has no ratio."""
    assert lists[name][0] == expected


def test_red_stars_are_carbon_stars_or_flagged_stars(lists):
    assert lists["red-stars"][0] == ["Carbonstar", "Redstar"]


@pytest.mark.parametrize(("name", "expected"), _cases(
    ("herschel-400", "NGC1055"),
    ("herschel-2500", "NGC1055", "NGC2775"),
))
def test_herschel_lists_follow_the_references_to_the_herschel_catalogue(lists, name, expected):
    """NGC1055 references a Herschel object of the list 400; NGC2775 one of the list 2500."""
    assert lists[name][0] == expected


def test_the_complete_list_leaves_out_the_solar_system(lists):
    labels = lists["complete-object-list"][0]
    assert "Mond" not in labels
    assert "Comet1" not in labels
    assert "Plainstar" in labels


def test_galaxies_and_groups_are_one_list(lists):
    assert lists["galaxies-and-groups"][0] == ["Arp10", "Arp20", "Hickson 1", "Messier 31", "NGC1", "NGC1055", "NGC2",
                                               "NGC224", "NGC2685", "NGC2775", "NGC3", "NGC4"]


@pytest.mark.parametrize(("name", "expected"), _cases(
    ("sketches-gallery", "Comet1", "Sketchy", "Sketchy too"),
    ("sketches-deepsky", "Sketchy", "Sketchy too"),
    ("sketches-comets", "Comet1"),
))
def test_sketch_lists_need_a_public_sketch(lists, name, expected):
    assert lists[name][0] == expected


def test_the_menu_counts_distinct_messier_names_and_distinct_sketches(lists):
    """Messier 16 and Messier 17 are one object with two names, so three names in two entries; the gallery has three
    different sketches (a.jpg is on two objects)."""
    assert lists["messier"][1] == 3
    assert lists["sketches-gallery"][1] == 3
    assert lists["complete-object-list"][1] == 23
