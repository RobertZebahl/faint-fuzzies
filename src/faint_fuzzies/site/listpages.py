"""The Website lists that have a page of their own: for each the file and the title, the pattern of the name
its rows are titled with, and the order of its rows. Which Objects belong to a list is decided in `domain.lists`;
only how a page shows them is here. A page's description, picture and image caption are content, not
structure - they come from page_descriptions.json (see read_page_descriptions), not from ListPage."""
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from faint_fuzzies.datadir import parse_json_file
from faint_fuzzies.domain.lists import Entry
from faint_fuzzies.site import menu

HERSCHEL_NAME = r"H\d+\.\d+(?:\.\d+)?"
PAGE_DESCRIPTIONS_FILE = "site/page_descriptions.json"


@dataclass(frozen=True)
class ListPage:
    """A Website list that has a page of its own: the file and the title, the pattern of the name its rows
    are titled with, and the order of its rows.

    :ivar file: the page's file name
    :ivar english: the title in English
    :ivar german: the title in German
    :ivar first_name: the name the title of a row shows: the last one that matches this whole; the row's
        first name otherwise
    :ivar sort_key: the order of the rows; that of the Global list when not given
    :ivar solar: whether the rows are those of Solar System objects, which have no constellation
    :ivar constellations: whether the page starts with the table of constellations to filter by
    """
    file: str
    english: str
    german: str
    first_name: str | None = None
    sort_key: Callable[[Entry], Any] | None = None
    solar: bool = False
    constellations: bool = True

    def title(self, locale: str) -> str:
        return self.english if locale == "en" else self.german


_PAGE_DESCRIPTION_KEYS = ("description_en", "description_de", "image", "image_source_en", "image_source_de")


def read_page_descriptions(root: Path) -> tuple[dict[str, dict[str, str]], str | None]:
    """The page_descriptions.json file, if there is one: a page name (a key of GLOBAL_PAGES) -> its
    description_en/description_de, its picture ("image", the same for both languages) and/or that
    picture's image_source_en/image_source_de. Meant to list every page (even with every value left ""),
    for a complete picture of which ones still need a description - but a page missing from it, or missing
    one of the keys, is not wrong, it simply shows none of it. Optional: a missing file is not wrong and
    gives ({}, None); an unreadable or malformed one gives ({}, why).

    :param root: the data directory
    :returns: the mapping (possibly empty), and why it is empty when that is a problem
    """
    path = root / PAGE_DESCRIPTIONS_FILE
    if not path.is_file():
        return {}, None
    data, why = parse_json_file(path)
    if why:
        return {}, why
    if not isinstance(data, dict) or not all(
            isinstance(entry, dict) and all(key in _PAGE_DESCRIPTION_KEYS for key in entry)
            and all(isinstance(value, str) for value in entry.values())
            for entry in data.values()):
        return {}, (f"must be a JSON object of page names to an object of {', '.join(_PAGE_DESCRIPTION_KEYS)}, "
                    "each a string")
    return data, None


def describe(page_descriptions: dict[str, dict[str, str]], name: str, locale: str) -> str | None:
    """The description of the page `name` shows under its title, if page_descriptions.json gives one.

    :param page_descriptions: as read_page_descriptions gives it
    :param name: the page's name, a key of GLOBAL_PAGES
    :param locale: "en" or "de"
    :returns: the description, or None when there is none
    """
    return page_descriptions.get(name, {}).get(f"description_{locale}") or None


def page_image(page_descriptions: dict[str, dict[str, str]], name: str) -> str | None:
    """The picture shown at the top of the page `name`, if page_descriptions.json gives one - the same
    picture for both languages, unlike its description or caption.

    :param page_descriptions: as read_page_descriptions gives it
    :param name: the page's name, a key of GLOBAL_PAGES
    :returns: the picture's path, or None when there is none
    """
    return page_descriptions.get(name, {}).get("image") or None


def image_caption(page_descriptions: dict[str, dict[str, str]], name: str, locale: str) -> str | None:
    """What the page `name`'s image (page_image) shows, if page_descriptions.json gives one.

    :param page_descriptions: as read_page_descriptions gives it
    :param name: the page's name, a key of GLOBAL_PAGES
    :param locale: "en" or "de"
    :returns: the caption, or None when there is none
    """
    return page_descriptions.get(name, {}).get(f"image_source_{locale}") or None


def _catalogue_number(pattern: str) -> Callable[[Entry], int]:
    """The number of the last name that matches `pattern` (its first group); a Group without a name is
    ordered by its group names.

    :param pattern: the regular expression to match, with the number as its first group
    :returns: a sort key function for ListPage.sort_key, which raises ValueError when an entry's names
        (or group names) do not match `pattern`
    """
    regex = re.compile(pattern)

    def key(entry: Entry) -> int:
        text = ",".join(entry.unit.names or entry.unit.groups)
        match = regex.match(text)
        if not match:
            raise ValueError(f"no catalogue number in the names of {text!r}")
        return int(match.group(1))
    return key


_HERSCHEL = re.compile(r".*H(\d+)\.(\d+)(\.\d+)?")


def _herschel_number(entry: Entry) -> tuple[int, ...]:
    """H400.5.2 is ordered as (400, 5, 2), H1.2 as (1, 2, 0).

    :param entry: the entry to order
    :returns: the sort key, or an empty tuple when the entry has no Herschel name
    """
    match = _HERSCHEL.match(",".join(entry.unit.names))
    if not match:
        return ()
    return int(match.group(1)), int(match.group(2)), int(match.group(3)[1:]) if match.group(3) else 0


def _files() -> dict[str, str]:
    """The file of every list in the menu.

    :returns: list name -> file name
    """
    entries = [e for group in (menu.OBSERVATIONS, menu.BY_TYPE, menu.SPECIAL_GALAXIES, menu.SKETCHES) for e in group
               if isinstance(e, tuple)]
    return {name: file for name, file, _english, _german in entries if name is not None}


_FILE = _files()


def _page(name: str, english: str, german: str, **more: Any) -> tuple[str, ListPage]:
    """Builds one GLOBAL_PAGES entry, looking the file up from `_FILE` by `name` so it does not have to be
    repeated at every call site.

    :param name: the list's name, a key of `_FILE`
    :param english: the title in English
    :param german: the title in German
    :param more: any other ListPage field
    :returns: (name, the built ListPage)
    """
    return name, ListPage(_FILE[name], english, german, **more)


_COMPLETE_OBJECT_LIST = cast("tuple[str, str, str, str]", menu.OBSERVATIONS[1])  # menu.OBSERVATIONS mixes in
# section markers (plain strings) and one (None, ...) header entry; index 1 is always this one, named, entry

GLOBAL_PAGES: dict[str, ListPage] = dict([
    # the complete list and the lists by type: the title is the name in the menu
    *(_page(name, english, german) for name, _file, english, german in [_COMPLETE_OBJECT_LIST, *menu.BY_TYPE]),
    _page("red-stars", "Carbon & Red Stars", "Kohlenstoffsterne & Rote Sterne"),
    _page("berkeley-clusters", "Open Clusters of the Berkeley Catalogue", "Offene Sternhaufen des Berkeley-Katalogs",
          first_name=r"Berkeley \d+", sort_key=_catalogue_number(r".*Berkeley (\d+).*")),
    _page("king-clusters", "Open Clusters of the King Catalogue", "Offene Sternhaufen des King-Katalogs",
          first_name=r"King \d+", sort_key=_catalogue_number(r".*King (\d+).*")),
    _page("abell-planetary-nebulae", "Planetary Nebulae of the Abell Catalogue",
          "Planetarische Nebel des Abell-Katalogs",
          first_name=r"Abell \d+", sort_key=_catalogue_number(r".*Abell (\d+).*")),
    _page("local-group", "Galaxies of the Local Group", "Galaxien der Lokalen Gruppe"),
    _page("hickson-groups", "Hickson Compact Groups", "Hickson-Gruppen",
          first_name=r"Hickson \d+", sort_key=_catalogue_number(r".*Hickson (\d+).*")),
    _page("arp-galaxies", "Galaxies of the Arp Catalogue", "Galaxien des Arp-Katalogs",
          first_name=r"Arp\d+", sort_key=_catalogue_number(r".*Arp(\d+).*")),
    _page("ring-galaxies", "Ring Galaxies", "Ringgalaxien"),
    _page("thin-galaxies", "Thin Galaxies", "Schmale Galaxien"),
    _page("superthin-galaxies", "Superthin Galaxies", "Besonders schmale Galaxien"),
    _page("messier", "Messier List", "Messier-Liste",
          first_name=r"Messier \d+", sort_key=_catalogue_number(r".*Messier (\d+).*")),
    _page("herschel-400", "Herschel 400 List", "Herschel-400-Liste",
          first_name=HERSCHEL_NAME, sort_key=_herschel_number),
    _page("herschel-2500", "Herschel 2500 List", "Herschel-2500-Liste",
          first_name=HERSCHEL_NAME, sort_key=_herschel_number),
    # the sketch pages: the same rows, of the objects with a sketch; the Solar System ones show no constellation
    _page("sketches-deepsky", "Sketches (Deepsky)", "Zeichnungen (Deepsky)"),
    _page("sketches-comets", "Sketches (Comets)", "Zeichnungen (Kometen)", solar=True, constellations=False),
    _page("sketches-planets", "Sketches (Planets)", "Zeichnungen (Planeten)", solar=True, constellations=False),
    _page("sketches-moon", "Sketches (Moon)", "Zeichnungen (Mond)", solar=True, constellations=False),
    _page("sketches-sun", "Sketches (Sun)", "Zeichnungen (Sonne)", solar=True, constellations=False),
    # the project of the galaxies behind Messier 44: a picture of the cluster instead of the table of constellations
    ("galaxies-in-messier-44", ListPage(
        "project-galaxies-in-messier-44.php", "Galaxies in Messier 44", "Galaxien in Messier 44",
        constellations=False)),
])

# the sketch gallery is a page of its own (see `gallery`), not a list of rows
GALLERY = ListPage(_FILE["sketches-gallery"], "Sketches (Gallery)", "Zeichnungen (Galerie)")
