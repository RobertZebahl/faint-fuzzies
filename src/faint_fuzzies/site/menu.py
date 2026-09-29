"""The menu every page carries, for one language: the page tree of the previous site, with the number of
entries beside each list. The links are the file names of the pages; a page that is not generated yet is
still linked, since it exists on the site. A link's own label is content, not structure - it comes from
site/static/php/page_content.php's menu_en/menu_de, looked up by the template itself (see menu_label
there), not from here."""
from typing import Any

from faint_fuzzies.site.text import quote_url

# (list name, file); the list name is that of a Global sublist whose size the menu shows, and the key its
# label is looked up by (see page_content.php)
OBSERVATIONS = [
    ("remarks", "observations-remarks.php"),
    ("complete-object-list", "observations-complete-object-list.php"),
    "by-type",
    ("red-stars", "observations-red-stars.php"),
    ("berkeley-clusters", "observations-open-clusters-berkeley.php"),
    ("king-clusters", "observations-open-clusters-king.php"),
    ("abell-planetary-nebulae", "observations-planetary-nebulae-abell.php"),
    "special-galaxies",
    ("messier", "observations-messier.php"),
    ("herschel-400", "observations-herschel-400.php"),
    ("herschel-2500", "observations-herschel-2500.php"),
]
BY_TYPE = [
    ("double-stars", "observations-double-stars.php"),
    ("asterisms", "observations-asterisms.php"),
    ("open-clusters", "observations-open-clusters.php"),
    ("globular-clusters", "observations-globular-clusters.php"),
    ("planetary-nebulae", "observations-planetary-nebulae.php"),
    ("bright-nebulae", "observations-bright-nebulae.php"),
    ("dark-nebulae", "observations-dark-nebulae.php"),
    ("galaxies-and-groups", "observations-galaxies.php"),
]
SPECIAL_GALAXIES = [
    ("local-group", "observations-galaxies-local-group.php"),
    ("hickson-groups", "observations-galaxies-hickson-groups.php"),
    ("arp-galaxies", "observations-galaxies-arp.php"),
    ("ring-galaxies", "observations-galaxies-ring-galaxies.php"),
    ("thin-galaxies", "observations-galaxies-thin-galaxies.php"),
    ("superthin-galaxies", "observations-galaxies-superthin-galaxies.php"),
]
SKETCHES = [
    ("sketches-gallery", "sketches-gallery.php"),
    ("sketches-deepsky", "sketches-deepsky.php"),
    ("sketches-comets", "sketches-comets.php"),
    ("sketches-planets", "sketches-planets.php"),
    ("sketches-moon", "sketches-moon.php"),
    ("sketches-sun", "sketches-sun.php"),
]
UNCOUNTED = {"remarks", "sketches-planets", "sketches-moon", "sketches-sun"}  # entries whose menu shows no number
# (key, file, both) - "key" is also looked up by page_content.php; "both" is whether the entry is linked
# for English too (the menu links grazing occultations for German only, like marketplace - the page itself
# is written in both languages)
PROJECTS = [
    ("project-double-stars", "project-double-stars.php?index=True", True),
    ("project-deep-sky-with-binoculars", "project-deep-sky-with-binoculars.php?index=True", True),
    ("project-skyguide", "project-skyguide.php", True),
    ("galaxies-in-messier-44", "project-galaxies-in-messier-44.php", True),
    ("project-grazing-occultations", "project-grazing-occultations.php", False),
]


def menu(locale: str, counts: dict[str, int]) -> list[dict[str, Any]]:
    """The menu as the navigation template reads it; every label is a lookup key, not text (see
    page_content.php's menu_label).

    :param locale: "en" or "de"
    :param counts: the name of a list -> its size
    :returns: the navigation template's values
    """
    english = locale == "en"

    def link(_entry: tuple) -> dict[str, Any]:
        _name, _file = _entry
        count = counts[_name] if _name not in UNCOUNTED and _name in counts else None
        return {"PAGE_KEY": _name, "COUNT": count, "LINK": quote_url(_file)}

    observations: list[dict[str, Any]] = []
    for entry in OBSERVATIONS:
        if entry == "by-type":
            observations.append({"PAGE_KEY": "by-type", "LINK_LIST": [link(e) for e in BY_TYPE]})
        elif entry == "special-galaxies":
            observations.append({"PAGE_KEY": "special-galaxies", "LINK_LIST": [link(e) for e in SPECIAL_GALAXIES]})
        elif isinstance(entry, tuple):
            observations.append(link(entry))

    projects = []
    for name, file, both in PROJECTS:
        if english and not both:
            continue
        projects.append({"PAGE_KEY": name, "COUNT": None, "LINK": _project_link(file)})

    result: list[dict[str, Any]] = [
        {"PAGE_KEY": "home", "COUNT": None, "LINK": "home.php"},
        {"PAGE_KEY": "equipment", "COUNT": None, "LINK": "equipment.php"},
        {"PAGE_KEY": "observations", "LINK_LIST": observations},
        {"PAGE_KEY": "sketches", "LINK_LIST": [link(e) for e in SKETCHES]},
        {"PAGE_KEY": "projects", "LINK_LIST": projects},
    ]
    if not english:
        result.append({"PAGE_KEY": "marketplace", "COUNT": None, "LINK": "marketplace.php"})
    result.append({"PAGE_KEY": "contact", "COUNT": None, "LINK": "contact.php"})
    return result


def _project_link(file: str) -> str:
    """The file quoted, a query left as written (?index=True).

    :param file: the file, with its query string if it has one
    :returns: the quoted link
    """
    name, question, query = file.partition("?")
    return quote_url(name) + question + query
