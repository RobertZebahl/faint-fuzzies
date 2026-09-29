"""The sketch gallery: one card per Sketch in each Gallery group it falls into, the card titled with every Object the
Sketch shows. The groups, their order, the precedence of an Object's group and the titles are those of the previous
tool. Nothing here renders anything."""
from collections import defaultdict
from typing import Any

from faint_fuzzies.domain.lists import Entry
from faint_fuzzies.domain.model import Object, ObjectAttribute
from faint_fuzzies.domain.model import ObjectType as T
from faint_fuzzies.site.listpages import GLOBAL_PAGES
from faint_fuzzies.site.objects import SKETCHES_FOLDER, SiteData
from faint_fuzzies.site.text import localized_names, quote_anchor

# the Gallery groups in the order of the page; a group's own label is content, not structure - it comes
# from site/static/php/page_content.php's gallery_en/gallery_de (see gallery_label there), not from here
GROUPS = [
    "red-stars", "double-stars", "asterisms", "open-clusters", "globular-clusters", "planetary-nebulae",
    "bright-nebulae", "dark-nebulae", "galaxies-and-groups", "miscellaneous", "sketches-comets",
    "sketches-planets", "sketches-moon", "sketches-sun",
]
SOLAR_SYSTEM_GROUPS = ("sketches-comets", "sketches-planets", "sketches-moon", "sketches-sun")
FOUR_COLUMNS = ("sketches-planets", "sketches-moon", "sketches-sun")  # the others have three

# the groups that a single type puts an Object in, in the order they are tried
_BY_TYPE = [
    ("double-stars", (T.DOUBLE_STAR,)),
    ("asterisms", (T.ASTERISM,)),
    ("open-clusters", (T.OPEN_CLUSTER,)),
    ("globular-clusters", (T.GLOBULAR_CLUSTER,)),
    ("planetary-nebulae", (T.PLANETARY_NEBULA,)),
    ("bright-nebulae", (T.BRIGHT_NEBULA,)),
    ("dark-nebulae", (T.DARK_NEBULA,)),
]


def gallery_group(obj: Object) -> str:
    """The Gallery group of an Object: the first of these its types fit.

    :param obj: the Object to classify
    :returns: the group's key, a key of GROUPS
    """
    types = obj.types
    if T.CARBON_STAR in types or obj.record.get(ObjectAttribute.RED_STARS_LIST):
        return "red-stars"
    for key, wanted in _BY_TYPE:
        if any(t in types for t in wanted):
            return key
    if T.GALAXY in types or T.GALAXY_GROUP in types:
        return "galaxies-and-groups"
    if T.COMET in types:
        return "sketches-comets"
    if T.PLANET in types:
        return "sketches-planets"
    if "Moon" in obj.names:
        return "sketches-moon"
    if "Sun" in obj.names:
        return "sketches-sun"
    return "miscellaneous"


def _link_page(obj: Object) -> str:
    """The page an Object of the gallery is linked to: that of its list.

    :param obj: the Object to link
    :returns: the file name of the Object's list page
    """
    name = gallery_group(obj)
    if name == "miscellaneous":  # a cluster of galaxies is not in the group of the galaxies, but is listed with them
        name = "galaxies-and-groups" if T.GALAXY_CLUSTER in obj.types else "complete-object-list"
    return GLOBAL_PAGES[name].file


def _title_and_link(obj: Object, locale: str) -> dict[str, str]:
    """The title and the link target of an Object shown on a gallery card: its name(s) (falling back to its
    group), with its type and constellation added when it has any, and a link to its anchor on its list page
    (the Moon and the Sun are not anchored, as their pages have only one entry).

    :param obj: the Object to title and link
    :param locale: "en" or "de"
    :returns: OBJECT_LINK_NAME and OBJECT_LINK for the gallery card template
    """
    names = localized_names(str(obj.record.get(ObjectAttribute.NAME) or ""), locale) or localized_names(
        str(obj.record.get(ObjectAttribute.GROUP) or ""), locale)
    first = names[0]
    if names[-1].startswith("WDS"):
        names = names[:-1]
    title = ", ".join(names)
    link = _link_page(obj)
    if "Moon" not in obj.names and "Sun" not in obj.names:
        link += f"#{quote_anchor(first)}"
    attributes = []
    if obj.types and (T.SOLAR_SYSTEM not in obj.types or T.COMET in obj.types):
        attributes.append(T.CARBON_STAR.value if T.CARBON_STAR in obj.types else obj.types[0].value)
    if obj.constellation:
        attributes.append(obj.constellation)
    if attributes:
        title = f"{title} ({', '.join(attributes)})"
    return {"OBJECT_LINK_NAME": title, "OBJECT_LINK": link}


def gallery_page(entries: list[Entry], locale: str, site: SiteData) -> dict[str, Any]:
    """The values of the gallery template for the entries with a sketch, in the order of the Global list.
    The page's own title is not here - the template looks it up itself (see site/static/php/page_content.php).

    :param entries: the Global list's entries
    :param locale: "en" or "de"
    :param site: the shared row-building data (observer names, sketch folders, ...)
    :returns: the gallery template's values
    """
    entries_by_group: dict[str, list[Entry]] = defaultdict(list)
    shown_in: dict[str, dict[str, list[Entry]]] = defaultdict(dict)  # sketch -> group -> the entries showing it
    sketches_of_group: dict[str, set[str]] = defaultdict(set)
    groups_of_sketch: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        group = gallery_group(entry.unit)
        for found in entry.observations:
            for name in found.observation.sketches:
                entries_by_group[group].append(entry)
                link = f"{SKETCHES_FOLDER}/{get_folder(found.observation, site)}/{name}"
                shown_in[link].setdefault(group, []).append(entry)
                sketches_of_group[group].add(link)
                groups_of_sketch[link].add(group)

    toc_deepsky, toc_solar, groups = [], [], []
    for key in GROUPS:
        if key not in entries_by_group:
            continue
        anchor = quote_anchor(key)
        toc = {"GROUP_KEY": key, "GROUP_NAME_ANCHOR": anchor, "NUMBER_OF_SKETCHES": len(sketches_of_group[key])}
        (toc_solar if key in SOLAR_SYSTEM_GROUPS else toc_deepsky).append(toc)
        cards = []
        for entry in entries_by_group[key]:
            for found in entry.observations:
                for sketch_name in found.observation.sketches:
                    link = f"{SKETCHES_FOLDER}/{get_folder(found.observation, site)}/{sketch_name}"
                    if key not in groups_of_sketch[link]:
                        continue  # the card of this sketch is in this group already
                    objects = [_title_and_link(e.unit, locale) for group in shown_in[link]
                               for e in shown_in[link][group]]
                    cards.append({"OBJECT_LIST": objects, "SKETCH": link,
                                  "OBSERVER": site.observer_name(get_folder(found.observation, site))})
                    groups_of_sketch[link].discard(key)
        groups.append({"COLUMN_COUNT": 4 if key in FOUR_COLUMNS else 3, "GROUP_KEY": key,
                       "GROUP_NAME_ANCHOR": anchor, "SKETCH_LIST": cards})
    return {"ENGLISH": locale == "en", "LOCALE": locale,
            "OBJECT_GROUP_LIST": groups, "OBJECT_GROUP_LIST_TOC_DEEPSKY": toc_deepsky,
            "OBJECT_GROUP_LIST_TOC_SOLARSYSTEM": toc_solar}


def get_folder(observation: Any, site: SiteData) -> str:
    """The folder of the sketches of an observation: the user's, or that of the observer who made it.

    :param observation: the observation to find the folder of
    :param site: the shared row-building data (observer names, sketch folders, ...)
    :returns: the folder's name
    """
    if observation.format is None:
        return site.owner_folder()
    return observation.observer.id if observation.observer else site.owner_folder()
