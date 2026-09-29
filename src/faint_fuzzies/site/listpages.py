"""The Website lists that have a page of their own: for each the file, the pattern of the name its rows
are titled with, and the order of its rows. Which Objects belong to a list is decided in `domain.lists`;
only how a page shows them is here. A page's title, description, picture and image caption are content,
not structure - they come from site/static/php/page_content.php, read by the template itself at page-view
time (see page_title, page_description, page_image, page_image_source there), not from ListPage."""
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from faint_fuzzies.domain.lists import Entry
from faint_fuzzies.site import menu

HERSCHEL_NAME = r"H\d+\.\d+(?:\.\d+)?"


@dataclass(frozen=True)
class ListPage:
    """A Website list that has a page of its own: the file, the pattern of the name its rows are titled
    with, and the order of its rows.

    :ivar file: the page's file name
    :ivar first_name: the name the title of a row shows: the last one that matches this whole; the row's
        first name otherwise
    :ivar sort_key: the order of the rows; that of the Global list when not given
    :ivar solar: whether the rows are those of Solar System objects, which have no constellation
    :ivar constellations: whether the page starts with the table of constellations to filter by
    """
    file: str
    first_name: str | None = None
    sort_key: Callable[[Entry], Any] | None = None
    solar: bool = False
    constellations: bool = True


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
    return dict(entries)


_FILE = _files()


def _page(name: str, **more: Any) -> tuple[str, ListPage]:
    """Builds one GLOBAL_PAGES entry, looking the file up from `_FILE` by `name` so it does not have to be
    repeated at every call site.

    :param name: the list's name, a key of `_FILE`
    :param more: any other ListPage field
    :returns: (name, the built ListPage)
    """
    return name, ListPage(_FILE[name], **more)


_COMPLETE_OBJECT_LIST = cast("tuple[str, str]", menu.OBSERVATIONS[1])  # menu.OBSERVATIONS mixes in section
# markers (plain strings) and the "remarks" header entry; index 1 is always this one, the complete list

GLOBAL_PAGES: dict[str, ListPage] = dict([
    *(_page(name) for name, *_rest in [_COMPLETE_OBJECT_LIST, *menu.BY_TYPE]),
    _page("red-stars"),
    _page("berkeley-clusters", first_name=r"Berkeley \d+", sort_key=_catalogue_number(r".*Berkeley (\d+).*")),
    _page("king-clusters", first_name=r"King \d+", sort_key=_catalogue_number(r".*King (\d+).*")),
    _page("abell-planetary-nebulae", first_name=r"Abell \d+", sort_key=_catalogue_number(r".*Abell (\d+).*")),
    _page("local-group"),
    _page("hickson-groups", first_name=r"Hickson \d+", sort_key=_catalogue_number(r".*Hickson (\d+).*")),
    _page("arp-galaxies", first_name=r"Arp\d+", sort_key=_catalogue_number(r".*Arp(\d+).*")),
    _page("ring-galaxies"),
    _page("thin-galaxies"),
    _page("superthin-galaxies"),
    _page("messier", first_name=r"Messier \d+", sort_key=_catalogue_number(r".*Messier (\d+).*")),
    _page("herschel-400", first_name=HERSCHEL_NAME, sort_key=_herschel_number),
    _page("herschel-2500", first_name=HERSCHEL_NAME, sort_key=_herschel_number),
    # the sketch pages: the same rows, of the objects with a sketch; the Solar System ones show no constellation
    _page("sketches-deepsky"),
    _page("sketches-comets", solar=True, constellations=False),
    _page("sketches-planets", solar=True, constellations=False),
    _page("sketches-moon", solar=True, constellations=False),
    _page("sketches-sun", solar=True, constellations=False),
    # the project of the galaxies behind Messier 44: a picture of the cluster instead of the table of constellations
    ("galaxies-in-messier-44", ListPage("project-galaxies-in-messier-44.php", constellations=False)),
])

# the sketch gallery is a page of its own (see `gallery`), not a list of rows
GALLERY = ListPage(_FILE["sketches-gallery"])
