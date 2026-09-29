"""The project pages: the values of the Double Stars page for one language, using the template's own variable
names (META_INFORMATION_LIST, DOUBLE_STARS, ...). Plain data, already escaped and formatted; see objects.py.

One page holds every list of the project: each entry says which lists it is in, and the page filters by the
`list` parameter of the address."""
from typing import Any

from faint_fuzzies.domain.lists import Entry, ListResult
from faint_fuzzies.domain.model import ObjectAttribute, ObservationAttribute
from faint_fuzzies.domain.observation import FoundObservation, Observation, OpticType
from faint_fuzzies.domain.observer import Observer, Scope
from faint_fuzzies.domain.seen import is_observation_seen
from faint_fuzzies.site import objects
from faint_fuzzies.site.objects import EN, SiteData
from faint_fuzzies.site.text import (
    HTML_MAGNITUDE,
    escape_html,
    quote_anchor,
    quote_url,
)

PHP_DOUBLE_STARS = "project-double-stars.php"
PROJECT_FOLDER = "../projects"  # + /<project>/<observer>/sketches or /photographs - a PROJECT-scope observer
# only (see _media_path); an OWNER/GLOBAL-scope one links from the shared top-level folder instead
PROJECT_KEY = {"double-stars": "double-stars", "deep-sky": "deep-sky-with-binoculars"}

# the lists of the Double Stars page: the name of the sublist ("complete" is the list ''), the address
# parameter, and the content key its title is looked up by (see project_list_title in page_content.php) -
# usually the same as the sublist name, but not always (a sublist can share a label with one of another
# project, or with nothing in particular - see page_content.php's own comment on its "project" entries)
DOUBLE_STAR_LISTS: list[tuple[str, str, str]] = [
    ("complete", "", "complete"),
    ("binoculars", "binoculars", "binoculars"),
    ("best-of", "best-of", "best-of"),
    ("recommendations", "recommendations", "recommendations"),
    ("multiples", "multiples", "multiples"),
    ("colored", "colored", "colored"),
    ("ra-00-06", "ra-00-06", "ra-00-06"),
    ("ra-06-12", "ra-06-12", "ra-06-12"),
    ("ra-12-18", "ra-12-18", "ra-12-18"),
    ("ra-18-24", "ra-18-24", "ra-18-24"),
    ("sketches", "sketches", "sketches"),
    ("photographs", "photographs", "photographs"),
    ("orbits", "orbits", "orbits"),
]


def double_stars_page(result: ListResult, locale: str, site: SiteData) -> dict[str, Any]:
    """The values of the page: the lists with their statistics and the entries with their observations.

    :param result: the project's entries
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :returns: the page's values
    """
    anchors_used: set[str] = set()
    entries = [_entry(entry, locale, site, anchors_used) for entry in result.entries]
    return {"META_INFORMATION_LIST": _lists(result, site), "DOUBLE_STARS": entries, "ENGLISH": locale == EN,
            "LOCALE": locale}


def _lists(result: ListResult, site: SiteData) -> list[dict[str, Any]]:
    """The META_INFORMATION_LIST values: one entry per sublist, with its title's content key and statistics.

    :param result: the project's entries
    :param site: the shared row-building data (for the observer list)
    :returns: the sublists' values
    """
    lists = []
    for sublist, key, sublist_key in DOUBLE_STAR_LISTS:
        members = [e for e in result.entries if sublist in e.sublists]
        observers = _observers(members, site)
        visual = photographic = sketches = photographs = 0
        for entry in members:
            for found in entry.observations:
                if found.observation.method == "photographic":
                    photographic += 1
                    photographs += len(found.observation.photographs)
                else:
                    visual += 1
                    sketches += len(found.observation.sketches)
        lists.append({
            "LIST": key, "SUBLIST_KEY": sublist_key, "NUMBER_OF_DOUBLE_STARS": len(members),
            "NUMBER_OF_OBSERVERS": len(observers), "NUMBER_OF_OBSERVATIONS_VISUAL": visual,
            "NUMBER_OF_OBSERVATIONS_PHOTOGRAPHIC": photographic, "NUMBER_OF_SKETCHES": sketches,
            "NUMBER_OF_PHOTOGRAPHS": photographs,
            "OBSERVER_LIST": [{"NAME": o.name, "CITY": o.city, "COUNTRY": o.country, "WEBSITE": o.website}
                              for o in observers]})
    return lists


def _observers(entries: list[Entry], site: SiteData) -> list[Observer]:
    """Who made the observations of the entries, by surname and first name.

    :param entries: the entries to list observers of
    :param site: the shared row-building data (for the fallback observer)
    :returns: the observers, deduplicated and sorted
    """
    people: dict[str, Observer] = {}
    for entry in entries:
        for found in entry.observations:
            person = _observer_of(found.observation, site)
            people.setdefault(person.id, person)
    return sorted(people.values(), key=lambda p: (p.surname, p.firstname))


def _observer_of(observation: Observation, site: SiteData) -> Observer:
    """The observer of an observation: its own when it has one, otherwise the user (by the observers file,
    or a made-up Observer of their folder when there is none).

    :param observation: the observation to find the observer of
    :param site: the shared row-building data (for the fallback observer)
    :returns: the observer
    """
    if observation.observer is not None:
        return observation.observer
    if site.observers is not None and site.observers.owner is not None:
        return site.observers.owner
    return Observer(site.owner_folder(), "", "", scope=Scope.OWNER)


def _entry(entry: Entry, locale: str, site: SiteData, anchors_used: set[str]) -> dict[str, Any]:
    """The values of one Double Stars entry: its components, observations (visual and photographic,
    grouped by observer) and the orbit diagrams of its pairs.

    :param entry: the entry to build the row for
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :param anchors_used: the anchors already given to an earlier entry, so this one's fresh links do not
        repeat them; updated in place with this entry's own anchors
    :returns: the entry's values
    """
    unit = entry.unit
    members = objects.sorted_members(entry, site) if unit.is_group else []
    pairs = members if unit.is_group else [unit]
    names = _names(entry, locale)
    equal_names = objects.members_share_a_name(unit, members) if unit.is_group else True
    # the raw value, un-rendered: the template renders it itself, with the hand-ported PHP mirror of
    # site/text.py's coordinate formatting (site/static/php/coordinates.php, shipped with the data directory)
    coordinates = objects.get_coordinates(unit, members, site)

    components = []
    _common, own_names_by_pair = objects.pair_name_commonality(pairs, locale)
    anchors = set(names)
    for pair, own_names in zip(pairs, own_names_by_pair):
        component = objects.get_pair_component(pair, site)
        anchors.update(own_names)
        row: dict[str, Any] = {}
        # the raw value, un-rendered: the template renders it itself, with the hand-ported PHP mirror of
        # site/text.py's magnitude formatting (site/static/php/magnitude.php, shipped with the data
        # directory) - the one place that needs the raw number, to compare it against its own threshold
        magnitude = objects.get_magnitude(pair, site)
        if magnitude:
            row["MAGNITUDE"] = magnitude
        if unit.is_group and not equal_names:
            row["PAIR_NAME"] = escape_html(", ".join(own_names))
        row["COMPONENT"] = escape_html(component["name"])
        row["SEPARATION"] = escape_html(component["separation"])
        row["POSITION_ANGLE"] = escape_html(component["angle"])
        row["YEAR"] = escape_html(component["year"])
        components.append(row)

    fresh = sorted(quote_anchor(a) for a in anchors if a not in anchors_used)
    anchors_used.update(anchors)
    filters = [key for sublist, key, _ in DOUBLE_STAR_LISTS if sublist in entry.sublists]

    labels = objects.build_member_labels(entry, locale, site)
    ordered = _by_observer(entry.observations)
    visual = [f for f in ordered if f.observation.method != "photographic"]
    photographic = [f for f in ordered if f.observation.method == "photographic"]
    visual.sort(key=lambda f: _visual_key(f.observation))  # equal keys stay in the order of _by_observer
    header = [_header(found, locale) for found in entry.header]
    orbit_images = objects.existing_orbit_images([s for pair in pairs for s in objects.get_orbits(pair, site)], site)
    if orbit_images:
        if header:
            header[0]["IMAGES"].extend(orbit_images)
        else:
            header.append({"DESCRIPTION": "", "IMAGES": list(orbit_images)})

    return {
        "LINK": quote_url(PHP_DOUBLE_STARS),
        "LIST_FILTER": " || ".join(f"$list == '{key}'" for key in filters),
        "NAME": escape_html(", ".join(names)), "CONSTELLATION": escape_html(unit.constellation),
        "COORDINATES": coordinates,
        "COMPONENTS": components, "ANCHOR": quote_anchor(names[0]), "ANCHOR_LIST": fresh,
        "RATING": entry.rounded_rating,
        "OBSERVATIONS_HEADER": header,
        "OBSERVATIONS_VISUAL": [_observation(f, locale, site, labels.get(id(f.object))) for f in visual],
        "OBSERVATIONS_PHOTOGRAPHIC": [_observation(f, locale, site, labels.get(id(f.object))) for f in photographic],
    }


def _by_observer(found: list[FoundObservation]) -> list[FoundObservation]:
    """The order: the user's observations, then those of the Global observers, then those of the
    project observers, by name, each in the order of the file.

    :param found: the observations to order
    :returns: the observations, ordered
    """
    def key(item: FoundObservation) -> tuple:
        observation = item.observation
        person = observation.observer
        rank = 0 if person is None else 1 if person.scope is Scope.GLOBAL else 2
        return (rank, (person.surname, person.firstname) if person else ("", ""), _line(observation.source))
    return sorted(found, key=key)


def _line(source: str) -> int:
    """The line of an observation in its file (`observer/file:line`), 0 for the user's own.

    :param source: the observation's source
    :returns: the line number, or 0 for the user's own observation
    """
    tail = source.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _names(entry: Entry, locale: str) -> list[str]:
    """An entry's names: the unit's own, a group name for a group or a name for a pair.

    :param entry: the entry to name
    :param locale: "en" or "de"
    :returns: the names
    """
    unit = entry.unit
    attribute = ObjectAttribute.GROUP if unit.is_group else ObjectAttribute.NAME
    return objects.get_display_names(unit.record.get(attribute), locale)


def _visual_key(observation: Observation) -> tuple:
    """The sort order of the visual observations: those with an optic before those without, binoculars by
    magnification then aperture, anything else by aperture then magnification.

    :param observation: the observation to find the sort key of
    :returns: the sort key
    """
    optic = observation.optic
    aperture = optic.aperture if optic is not None else None
    binoculars = optic is not None and optic.type is OpticType.BINOCULARS
    magnification = _magnification(observation)
    return (bool(aperture), not binoculars, (magnification if binoculars else aperture) or 0,
            (aperture if binoculars else magnification) or 0)


def _magnification(observation: Observation) -> int | None:
    """The observation's magnification: binoculars' own, otherwise the visibility entry's when it was
    noted, falling back to the optic's.

    :param observation: the observation to find the magnification of
    :returns: the magnification, or None when there is no optic or none is known
    """
    optic = observation.optic
    if optic is None:
        return None
    if optic.type is OpticType.BINOCULARS:
        return optic.magnification
    if observation.visibility:
        return observation.visibility[0].magnification
    return optic.magnification


def _optic_text(observation: Observation) -> tuple[str | None, str | None]:
    """How the observation's optic is shown: binoculars as "<magnification>x<aperture>", the naked eye as
    its content key (see head_label in site/static/php/description.php), a telescope as its aperture with
    the magnification in parentheses when known.

    :param observation: the observation to describe the optic of
    :returns: (the optic's text, its content key) - exactly one is given, or both are None when there is
        no optic or not enough is known to describe it
    """
    optic = observation.optic
    if optic is None:
        return None, None
    if optic.type is OpticType.BINOCULARS:
        return (f"{optic.magnification}x{optic.aperture}" if optic.aperture and optic.magnification
                else None), None
    if optic.type is OpticType.NAKED_EYE:
        return None, "naked-eye"
    text = None
    if optic.aperture:
        text = escape_html(f"{optic.aperture}mm")
        if _magnification(observation):
            text += escape_html(f" ({_magnification(observation)}x)")
    return text, None


def _location(person: Observer) -> str | None:
    if person.city and person.country:
        return f"{person.city} ({person.country})"
    return person.city or person.country or None


def _observation(found: FoundObservation, locale: str, site: SiteData, label: str | None) -> dict[str, Any]:
    """The values of one row of an entry's visual or photographic observations.

    :param found: the observation to describe
    :param locale: "en" or "de"
    :param site: the shared row-building data (for the fallback observer)
    :param label: what leads the description, when the observation was taken over from another pair
    :returns: the observation row's values
    """
    observation = found.observation
    person = _observer_of(observation, site)
    row: dict[str, Any] = {"OBSERVER_NAME": escape_html(person.name),
                           "OBSERVER_LOCATION": escape_html(_location(person))}
    optic, optic_key = _optic_text(observation)
    if optic is not None:
        row["OPTIC"] = optic
    elif optic_key is not None:
        row["OPTIC_KEY"] = optic_key
    # the local conditions near the object, then the description, led by the pair when it is one pair of a system's
    local_conditions = objects.local_conditions_items(observation.record)
    text = objects.build_description_text(observation.record, locale, label)
    row["LOCAL_CONDITIONS"] = local_conditions
    row["LOCAL_CONDITIONS_DOUBLE_BREAK"] = bool(local_conditions) and "\n\n" in text
    row["DESCRIPTION"] = escape_html(text)
    kind, names = ("photographs", observation.photographs) if observation.method == "photographic" else (
        "sketches", observation.sketches)
    row["IMAGES"] = [quote_url(f"{_media_path(person, kind, 'double-stars')}/{name}") for name in names]
    return row


def _media_path(person: Observer, kind: str, project: str) -> str:
    """Where a person's Sketch/Photograph files are linked from, everything up to the file name: the shared
    top-level folder for OWNER/GLOBAL scope (the same one the Global list uses - see objects.py), since a
    Sketch or Photograph of theirs is never only on one project; the project's own per-observer folder for a
    PROJECT-scope observer, who has no presence outside the projects they contribute to.

    :param person: the observer whose files to link
    :param kind: "sketches" or "photographs"
    :param project: the project's name, a key of PROJECT_KEY
    :returns: the link's folder
    """
    if person.scope in (Scope.OWNER, Scope.GLOBAL):
        folder = objects.SKETCHES_FOLDER if kind == "sketches" else objects.PHOTOGRAPHS_FOLDER
        return f"{folder}/{person.id}"
    return f"{PROJECT_FOLDER}/{PROJECT_KEY[project]}/{person.id}/{kind}"


def _header(found: FoundObservation, locale: str) -> dict[str, Any]:
    """The values of an entry's header row: the object's general description (in `locale`) and its images.

    :param found: the header observation to describe
    :param locale: "en" or "de"
    :returns: the header row's values
    """
    observation = found.observation
    text = str(observation.record.get(
        ObservationAttribute.DESCRIPTION_EN if locale == EN else ObservationAttribute.DESCRIPTION_DE, "") or "")
    return {"DESCRIPTION": text,
            "IMAGES": [quote_url(f"{objects.IMAGES_FOLDER}/{name}") for name in observation.images]}


# --- Deep Sky With Binoculars

PHP_DEEP_SKY = "project-deep-sky-with-binoculars.php"

# (sublist name, address parameter, content key) - see DOUBLE_STAR_LISTS above for what the content key means
DEEP_SKY_LISTS: list[tuple[str, str, str]] = [
    ("complete", "", "complete"),
    ("asterisms", "asterisms", "asterisms"),
    ("open-clusters", "open-clusters", "open-clusters"),
    ("globular-clusters", "globular-clusters", "globular-clusters"),
    ("planetary-nebulae", "planetary-nebulae", "planetary-nebulae"),
    ("bright-nebulae", "bright-nebulae", "bright-nebulae"),
    ("dark-nebulae", "dark-nebulae", "dark-nebulae"),
    ("galaxies", "galaxies", "galaxies"),
    # distinct from the "messier" page's own "Messier List" title - this sublist means something narrower
    ("messier", "messier", "messier-objects"),
    ("best-of", "best-of", "best-of"),
    ("recommendations", "recommendations", "recommendations"),
    ("sketches", "sketches", "sketches"),
    ("ra-00-06", "ra-00-06", "ra-00-06"),
    ("ra-06-12", "ra-06-12", "ra-06-12"),
    ("ra-12-18", "ra-12-18", "ra-12-18"),
    ("ra-18-24", "ra-18-24", "ra-18-24"),
]


def deep_sky_page(result: ListResult, locale: str, site: SiteData) -> dict[str, Any]:
    """The values of the page: the lists with their statistics and the entries with their observations.

    :param result: the project's entries
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :returns: the page's values
    """
    anchors_used: set[str] = set()
    entries = [_deep_sky_entry(entry, locale, site, anchors_used) for entry in result.entries]
    return {"META_INFORMATION_LIST": _deep_sky_lists(result, site), "OBJECTS": entries,
            "ENGLISH": locale == EN, "LOCALE": locale}


def _deep_sky_lists(result: ListResult, site: SiteData) -> list[dict[str, Any]]:
    """The META_INFORMATION_LIST values: one entry per sublist, with its title's content key and statistics.

    :param result: the project's entries
    :param site: the shared row-building data (for the observer list)
    :returns: the sublists' values
    """
    lists = []
    for sublist, key, sublist_key in DEEP_SKY_LISTS:
        members = [e for e in result.entries if sublist in e.sublists]
        observers = _observers(members, site)
        count = len(members)
        if sublist == "messier":  # only here: two objects with one Messier number (Messier 16) count once
            count = len({n for e in members for n in e.unit.names if n.startswith("Messier ")})
        lists.append({
            "LIST": key, "SUBLIST_KEY": sublist_key, "NUMBER_OF_OBJECTS": count,
            "NUMBER_OF_OBSERVERS": len(observers),
            "NUMBER_OF_OBSERVATIONS": sum(len(e.observations) for e in members),
            "NUMBER_OF_SKETCHES": sum(len(f.observation.sketches) for e in members for f in e.observations),
            "OBSERVER_LIST": [{"NAME": o.name, "CITY": o.city, "COUNTRY": o.country, "WEBSITE": o.website}
                              for o in observers]})
    return lists


def _deep_sky_entry(entry: Entry, locale: str, site: SiteData, anchors_used: set[str]) -> dict[str, Any]:
    """The values of one Deep Sky With Binoculars entry: its DSS image (if cached) and observations, ordered
    by magnification then aperture.

    :param entry: the entry to build the row for
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :param anchors_used: the anchors already given to an earlier entry, so this one's fresh links do not
        repeat them; updated in place with this entry's own anchors
    :returns: the entry's values
    """
    obj = entry.unit
    names = objects.get_display_names(obj.record.get(ObjectAttribute.NAME), locale)
    row: dict[str, Any] = {
        "LINK": quote_url(PHP_DEEP_SKY),
        "LIST_FILTER": " || ".join(f"$list == '{key}'" for sublist, key, _ in DEEP_SKY_LISTS
                                   if sublist in entry.sublists)}
    image = objects.get_dss_image(site.data_dir, obj, site.dss_listings)
    if image is not None:
        row["IMAGE"] = f"{objects.DSS_FOLDER}/{image.thumbnail}"
        row["IMAGE_LINK"] = quote_url(f"{objects.DSS_FOLDER}/{image.full}")
        row["IMAGE_SOURCE_KEY"] = image.source.value
        row["IMAGE_FOV"] = escape_html(image.fov)
    # raw values, un-rendered: the template renders them itself, with the hand-ported PHP mirrors of
    # site/text.py's formatting (site/static/php/coordinates.php, size.php, shipped with the data directory)
    coordinates = objects.get_coordinates(obj, [], site)
    fresh = sorted(quote_anchor(a) for a in set(names) if a not in anchors_used)
    anchors_used.update(names)
    row.update({
        "NAME": escape_html(", ".join(names)), "CONSTELLATION": escape_html(obj.constellation),
        "MAGNITUDE": objects.get_magnitude(obj, site),
        "SIZE": str(obj.record.get(ObjectAttribute.SIZE, "")),
        "TYPE": escape_html(", ".join(t.value for t in obj.types)),
        "COORDINATES": coordinates,
        "ANCHOR": quote_anchor(names[0]), "ANCHOR_LIST": fresh, "RATING": entry.rounded_rating,
        "OBSERVATIONS_HEADER": [_header(found, locale) for found in entry.header],
    })
    ordered = _by_observer(entry.observations)
    ordered.sort(key=lambda f: (_deep_sky_magnification(f.observation) or 0, _aperture(f.observation) or 0))
    row["OBSERVATIONS"] = [_deep_sky_observation(f, locale, site) for f in ordered]
    return row


def _aperture(observation: Observation) -> int | None:
    """The observation's aperture; 0 for the naked eye (so it sorts before any instrument).

    :param observation: the observation to find the aperture of
    :returns: the aperture, or None when there is no optic
    """
    optic = observation.optic
    if optic is None:
        return None
    return 0 if optic.type is OpticType.NAKED_EYE else optic.aperture


def _deep_sky_magnification(observation: Observation) -> int | None:
    """The observation's magnification; 1 for the naked eye, the visibility entry's when noted, falling
    back to the optic's.

    :param observation: the observation to find the magnification of
    :returns: the magnification, or None when there is no optic or none is known
    """
    optic = observation.optic
    if optic is None:
        return None
    if optic.type is OpticType.NAKED_EYE:
        return 1
    if observation.visibility and observation.visibility[0].magnification:
        return observation.visibility[0].magnification
    return optic.magnification


def _deep_sky_observation(found: FoundObservation, locale: str, site: SiteData) -> dict[str, Any]:
    """The values of one row of a Deep Sky With Binoculars entry's observations.

    :param found: the observation to describe
    :param locale: "en" or "de"
    :param site: the shared row-building data (for the fallback observer)
    :returns: the observation row's values
    """
    observation = found.observation
    person = _observer_of(observation, site)
    record = observation.record
    row: dict[str, Any] = {"OBSERVER_NAME": escape_html(person.name),
                           "OBSERVER_LOCATION": escape_html(_location(person))}
    aperture = _aperture(observation)
    if aperture == 0:
        row["OPTIC_KEY"] = "naked-eye"
    elif aperture is not None:
        row["OPTIC"] = escape_html(f"{_deep_sky_magnification(observation)}x{aperture}")
    conditions: list[dict[str, Any]] = []
    if record.get(ObservationAttribute.BORTLE):
        conditions.append({"TEXT": escape_html(f"Bortle {record[ObservationAttribute.BORTLE]}")})
    if record.get(ObservationAttribute.SQM):
        conditions.append({"TEXT": escape_html(f"SQM {record[ObservationAttribute.SQM]}")})
    if record.get(ObservationAttribute.SQML):
        conditions.append({"TEXT": escape_html(f"SQM-L {record[ObservationAttribute.SQML]}")})
    if record.get(ObservationAttribute.NELM):
        nelm_text = str(record[ObservationAttribute.NELM]).replace(".", HTML_MAGNITUDE)
        conditions.append({"KEY": "nelm", "TEXT": f" {nelm_text}"})
    row["CONDITIONS"] = conditions
    row["SEEN"] = _seen(observation)
    local_conditions = objects.local_conditions_items(record)
    text = objects.build_description_text(record, locale, None)
    row["LOCAL_CONDITIONS"] = local_conditions
    row["LOCAL_CONDITIONS_DOUBLE_BREAK"] = bool(local_conditions) and "\n\n" in text
    row["DESCRIPTION"] = escape_html(text)
    row["IMAGES"] = [quote_url(f"{_media_path(person, 'sketches', 'deep-sky')}/{name}")
                     for name in observation.sketches]
    return row


def _seen(observation: Observation) -> bool | None:
    """The check mark: a failed observation is not seen; one of another observer is seen unless it failed; the
    user's own and a Global observer's are only marked when they state a result.

    :param observation: the observation to check
    :returns: whether it is seen, or None to show no check mark at all
    """
    if observation.format in (None, "global") and (not observation.visibility
                                                          or observation.visibility[0].result is None):
        return None
    return is_observation_seen(observation, False)
