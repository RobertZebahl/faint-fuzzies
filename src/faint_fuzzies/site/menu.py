"""The menu every page carries, for one language: the page tree of the previous site, with the number of
entries beside each list. The links are the file names of the pages; a page that is not generated yet is
still linked, since it exists on the site."""
from typing import Any

from faint_fuzzies.site.text import quote_url

# (list name, file, English, German); the list name is that of a Global sublist whose size the menu shows
OBSERVATIONS = [
    (None, "observations-remarks.php", "Remarks about the observations", "Hinweise zu den Beobachtungen"),
    ("complete-object-list", "observations-complete-object-list.php", "Complete Object List",
     "Vollständige Objektliste"),
    "by-type",
    ("red-stars", "observations-red-stars.php", "Carbon & Red Stars", "Kohlenstoffsterne & Rote Sterne"),
    ("berkeley-clusters", "observations-open-clusters-berkeley.php", "Berkeley Clusters", "Berkeley-Haufen"),
    ("king-clusters", "observations-open-clusters-king.php", "King Clusters", "King-Haufen"),
    ("abell-planetary-nebulae", "observations-planetary-nebulae-abell.php", "Abell Planetary Nebulae",
     "Abell Planetarische Nebel"),
    "special-galaxies",
    ("messier", "observations-messier.php", "Messier List", "Messier-Liste"),
    ("herschel-400", "observations-herschel-400.php", "Herschel 400 List", "Herschel-400-Liste"),
    ("herschel-2500", "observations-herschel-2500.php", "Herschel 2500 List", "Herschel-2500-Liste"),
]
BY_TYPE = [
    ("double-stars", "observations-double-stars.php", "Double Stars", "Doppelsterne"),
    ("asterisms", "observations-asterisms.php", "Asterisms", "Asterismen"),
    ("open-clusters", "observations-open-clusters.php", "Open Clusters", "Offene Sternhaufen"),
    ("globular-clusters", "observations-globular-clusters.php", "Globular Clusters", "Kugelsternhaufen"),
    ("planetary-nebulae", "observations-planetary-nebulae.php", "Planetary Nebulae", "Planetarische Nebel"),
    ("bright-nebulae", "observations-bright-nebulae.php", "Bright Nebulae", "Helle Nebel"),
    ("dark-nebulae", "observations-dark-nebulae.php", "Dark Nebulae", "Dunkelnebel"),
    ("galaxies-and-groups", "observations-galaxies.php", "Galaxies & Groups", "Galaxien & Gruppen"),
]
SPECIAL_GALAXIES = [
    ("local-group", "observations-galaxies-local-group.php", "Galaxies of the Local Group",
     "Galaxien der Lokalen Gruppe"),
    ("hickson-groups", "observations-galaxies-hickson-groups.php", "Hickson Compact Groups", "Hickson-Gruppen"),
    ("arp-galaxies", "observations-galaxies-arp.php", "Arp Galaxies", "Arp-Galaxien"),
    ("ring-galaxies", "observations-galaxies-ring-galaxies.php", "Ring Galaxies", "Ringgalaxien"),
    ("thin-galaxies", "observations-galaxies-thin-galaxies.php", "Thin Galaxies 1:5", "Schmale Galaxien 1:5"),
    ("superthin-galaxies", "observations-galaxies-superthin-galaxies.php", "Superthin Galaxies 1:7",
     "Besonders schmale Galaxien 1:7"),
]
SKETCHES = [
    ("sketches-gallery", "sketches-gallery.php", "Gallery", "Galerie"),
    ("sketches-deepsky", "sketches-deepsky.php", "Deepsky", "Deepsky"),
    ("sketches-comets", "sketches-comets.php", "Comets", "Kometen"),
    ("sketches-planets", "sketches-planets.php", "Planets", "Planeten"),
    ("sketches-moon", "sketches-moon.php", "Moon", "Mond"),
    ("sketches-sun", "sketches-sun.php", "Sun", "Sonne"),
]
UNCOUNTED = {"sketches-planets", "sketches-moon", "sketches-sun"}  # lists whose menu entry shows no number
PROJECTS = [
    ("project-double-stars.php?index=True", "Double Stars", "Doppelsterne", True),
    ("project-deep-sky-with-binoculars.php?index=True", "Deep Sky with Binoculars", "Deep-Sky mit dem Fernglas", True),
    ("project-skyguide.php", "Skyguide", "Skyguide", True),
    ("project-galaxies-in-messier-44.php", "Galaxies in Messier 44", "Galaxien in Messier 44", True),
    ("project-grazing-occultations.php", None, "Streifende Sternbedeckungen durch den Mond", False),  # German only
]


def menu(locale: str, counts: dict[str, int]) -> list[dict[str, Any]]:
    """The menu as the navigation template reads it.

    :param locale: "en" or "de"
    :param counts: the name of a list -> its size
    :returns: the navigation template's values
    """
    english = locale == "en"

    def link(_entry: tuple) -> dict[str, str]:
        _name, _file, _en, _de = _entry
        text = _en if english else _de
        if _name is not None and _name not in UNCOUNTED:
            text += f" ({counts[_name]})"
        return {"LINK_NAME": text, "LINK": quote_url(_file)}

    observations: list[dict[str, Any]] = []
    for entry in OBSERVATIONS:
        if entry == "by-type":
            observations.append({"LINK_NAME": "Objects by type" if english else "Objekte nach Typ",
                                 "LINK_LIST": [link(e) for e in BY_TYPE]})
        elif entry == "special-galaxies":
            observations.append({"LINK_NAME": "Special Galaxies" if english else "Spezielle Galaxien",
                                 "LINK_LIST": [link(e) for e in SPECIAL_GALAXIES]})
        elif isinstance(entry, tuple):
            observations.append(link(entry))

    projects = []
    for file, en, de, both in PROJECTS:
        if english and not both:
            continue
        projects.append({"LINK_NAME": en if english else de, "LINK": _project_link(file)})

    result: list[dict[str, Any]] = [
        {"LINK_NAME": "Home" if english else "Start", "LINK": "home.php"},
        {"LINK_NAME": "Equipment" if english else "Ausrüstung", "LINK": "equipment.php"},
        {"LINK_NAME": "Observations" if english else "Beobachtungen", "LINK_LIST": observations},
        {"LINK_NAME": "Sketches" if english else "Zeichnungen", "LINK_LIST": [link(e) for e in SKETCHES]},
        {"LINK_NAME": "Projects" if english else "Projekte", "LINK_LIST": projects},
    ]
    if not english:
        result.append({"LINK_NAME": "Marktplatz", "LINK": "marketplace.php"})
    result.append({"LINK_NAME": "Contact" if english else "Kontakt", "LINK": "contact.php"})
    return result


def _project_link(file: str) -> str:
    """The file quoted, a query left as written (?index=True).

    :param file: the file, with its query string if it has one
    :returns: the quoted link
    """
    name, question, query = file.partition("?")
    return quote_url(name) + question + query
