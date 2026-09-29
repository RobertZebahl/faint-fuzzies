"""The row of an Object on a list page: the values the row template shows, for one language.

The names of the values match the templates' own variable names (OBJECT_TITLE, OBJECT_INFO, ...), which are
used unchanged. Everything is plain data (strings, lists, dicts), already in its final form: escaped and
formatted as HTML exactly where the template expects it. Nothing here renders anything.
"""
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.lists import Entry
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObservationAttribute
from faint_fuzzies.domain.model import ObjectType as T
from faint_fuzzies.domain.observation import (
    Color,
    Difficulty,
    FoundObservation,
    Grade,
    Observation,
    OpticType,
    is_header,
)
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.domain.references import References, wds_reference
from faint_fuzzies.domain.sorting import natural_sort_key
from faint_fuzzies.media_pool import OrbitSolution, orbit_cache_path
from faint_fuzzies.site.media import SOURCE_LABELS, get_dss_image
from faint_fuzzies.site.text import (
    HTML_MAGNITUDE,
    escape_html,
    format_coordinates,
    format_magnitude,
    format_magnitude_pair,
    format_size,
    localized_names,
    quote_anchor,
    quote_url,
)

DE, EN = "de", "en"
IMAGES_FOLDER = "../images"
DSS_FOLDER = "../images/dss"
SKETCHES_FOLDER = "../sketches"
PHOTOGRAPHS_FOLDER = "../photographs"
ORBITS_FOLDER = "../images/orbits"

COLOR_WHITE = "#FFFFFF"
COLOR_RED = "#E61E11"
COLOR_ORANGE = "#E48319"
GRADE_STYLE = {  # result -> (color, text in English, text in German)
    Difficulty.EASY: ("#24B92C", "EASY", "EINFACH"),
    Difficulty.MEDIUM: ("#CBE419", "MODERATE", "MITTEL"),
    Difficulty.HARD: (COLOR_ORANGE, "DIFFICULT", "SCHWER"),
    Difficulty.FAILED: ("#AA1309", "FAILED", "NICHT GESEHEN"),
    Color.RED: (COLOR_RED, "RED COLORED", "ROTFARBEN"),
    Color.ORANGE: (COLOR_ORANGE, "ORANGE COLORED", "ORANGEFARBEN"),
}


@dataclass
class SiteData:
    """What a row needs besides the entry: the observers, the readable names of instruments and where the
    caches of images are.

    :ivar observers: the observers, if known
    :ivar optic_names: an optic code -> its readable name
    :ivar data_dir: the data directory, for the image caches; None means no image is ever found
    :ivar references: the catalogue cross-references, for WDS lookups
    :ivar orbits: id(WDS pair) -> its orbital solutions
    :ivar dss_listings: the files of a DSS cache folder, listed once and kept here across calls
    """
    observers: Observers | None = None
    optic_names: dict[str, str] = field(default_factory=dict)
    data_dir: Path | None = None
    references: References | None = None
    orbits: dict[int, list[OrbitSolution]] = field(default_factory=dict)
    dss_listings: dict[Path, frozenset[str]] = field(default_factory=dict)

    def owner_folder(self) -> str:
        """:returns: the user's own observer id, or "own" when there is no observers file"""
        return self.observers.owner_id() if self.observers else "own"

    def observer_name(self, observer_id: str) -> str:
        """:param observer_id: the observer's id
        :returns: the observer's full name, or `observer_id` itself when the observer is unknown
        """
        observer = self.observers.get(observer_id) if self.observers else None
        return f"{observer.firstname} {observer.surname}" if observer else observer_id


def object_row(entry: Entry, locale: str, site: SiteData, first_name_pattern: str | None = None) -> dict[str, Any]:
    """The values of one row.

    :param entry: the entry to build the row for
    :param locale: "en" or "de"
    :param site: the shared row-building data (observers, instrument names, image caches)
    :param first_name_pattern: picks the name the title shows (the Messier and Herschel lists show the
        Messier or Herschel name); the first name when not given
    :returns: the row template's values
    :raises ValueError: when the Object has no name or group, or - for a non-Solar-System Object - has no
        type, no constellation, or no coordinates
    """
    obj = entry.unit
    english = locale == EN
    double_star = T.DOUBLE_STAR in obj.types
    row: dict[str, Any] = {"ENGLISH": english, "OBJECT_INFO": []}
    info = row["OBJECT_INFO"]

    names = get_display_names(obj.record.get(ObjectAttribute.NAME), locale)
    groups = get_display_names(obj.record.get(ObjectAttribute.GROUP), locale)
    if not names and not groups:
        raise ValueError("object without any name or group")
    types = obj.types
    solar = T.SOLAR_SYSTEM in types

    if not solar:
        if not names:
            names = groups
            info.append(_info("Name:", escape_html(", ".join(groups))))
        else:
            info.append(_info("Name:", escape_html(", ".join(names))))
            if groups:
                info.append(_info("Group:" if english else "Gruppe:", escape_html(", ".join(groups))))

    first_name = _first_name(names, first_name_pattern)
    first_type = None
    orbit_solutions: list[OrbitSolution] = []
    members = sorted_members(entry, site) if obj.is_group else []
    if not solar:
        if not types:
            raise ValueError(f"object {first_name} without any type")
        first_type = T.CARBON_STAR.value if T.CARBON_STAR in types else types[0].value
        info.append(_info("Type:" if english else "Typ:", escape_html(", ".join(t.value for t in types))))

        constellation = obj.constellation
        if not constellation:
            raise ValueError(f"object {first_name} without constellation")
        row["OBJECT_CONSTELLATION"] = constellation
        info.append(_info("Constellation:" if english else "Sternbild:", escape_html(constellation)))
        coordinates = format_coordinates(get_coordinates(obj, members, site))
        if coordinates is None:
            raise ValueError(f"object {first_name} without coordinates")
        info.append(_info("Coordinates:" if english else "Koordinaten:", f"{coordinates[0]} / {coordinates[1]}"))

        magnitude = format_magnitude(get_magnitude(obj, site)) or "-"
        size = format_size(str(obj.record.get(ObjectAttribute.SIZE, "")), with_angle=False) or "-"
        if obj.is_group:
            if not double_star:
                row["GROUP_MEMBER_HEAD"] = "Group Members:" if english else "Gruppenmitglieder:"
                row["GROUP_MEMBERS"] = [_group_member(member, locale) for member in members]
            else:
                _double_star_components(row, members, locale, site, members_share_a_name(obj, members))
                for member in members:
                    orbit_solutions.extend(get_orbits(member, site))
        elif not double_star:
            if T.STAR in types:
                info.append(_info("Brightness:" if english else "Helligkeit:", magnitude))
            else:
                info.append(_info("Brightness / Size:" if english else "Helligkeit / Größe:",
                                  f"{magnitude} / {size}"))
        else:
            _double_star_components(row, [obj], locale, site, True)
            orbit_solutions.extend(get_orbits(obj, site))

        image = get_dss_image(site.data_dir, obj, site.dss_listings)
        if image is not None:
            row["IMAGE"] = f"{DSS_FOLDER}/{image.thumbnail}"
            row["IMAGE_LINK"] = quote_url(f"{DSS_FOLDER}/{image.full}")
            label = escape_html(SOURCE_LABELS[image.source][locale])
            row["IMAGE_SOURCE"] = f"{label} - {escape_html(image.fov)}'&times;{escape_html(image.fov)}'"

    anchors = set(names)
    if double_star and obj.is_group and members:
        for member in members:
            anchors |= set(get_display_names(member.record.get(ObjectAttribute.NAME), locale))
    row["ANCHOR_LIST"] = sorted(({"ANCHOR": quote_anchor(n)} for n in anchors), key=lambda a: a["ANCHOR"])
    title = f"{first_name} ({first_type})" if first_type else first_name
    row["OBJECT_TITLE"] = escape_html(title)
    row["DESCRIPTIONS"] = _descriptions(entry, locale, site, orbit_solutions)
    return row


_WDS_ID = re.compile(r"WDS\d{5}[+-]\d{4}")


def get_display_names(value: Any, locale: str | None) -> list[str]:
    """The names of a NAME or GROUP value as the pages show them: without the WDS id that ends the names of a
    double star system.

    :param value: the record's NAME or GROUP value
    :param locale: "en" or "de", or None for the raw (unlocalized) names
    :returns: the names
    """
    names = localized_names(str(value or ""), locale)
    return names[:-1] if names and _WDS_ID.fullmatch(names[-1]) else names


def _info(prop: str, value: str) -> dict[str, str]:
    return {"OBJECT_INFO_PROPERTY": prop, "OBJECT_INFO_VALUE": value}


def _first_name(names: list[str], pattern: str | None) -> str:
    """The name of the title: the first, or the last one that matches `pattern` whole; "Arp10" is written
    "Arp 10", and "STF2155 & WAL79" as "STF 2155 & WAL 79" (a part without letters and digits is dropped).

    :param names: the Object's names
    :param pattern: a regular expression the title's name must match whole; the first name when not given
    :returns: the formatted title name
    """
    if pattern:
        chosen = ""
        for name in names:
            if re.match(f"^{pattern}$", name):
                chosen = name
    else:
        chosen = names[0]
    if re.match(r"^Arp\d+$", chosen):
        chosen = chosen.replace("Arp", "Arp ")
    modified = []
    for part in (e.strip() for e in chosen.split("&")):
        match = re.match(r"^([A-Za-z]+)(\d+.*)", part)
        if match:
            modified.append(f"{match.group(1)} {match.group(2)}")
    return " & ".join(modified) if modified else chosen


def _group_member(member: Object, locale: str) -> dict[str, str]:
    """The values of one row of a (non-double star) group's member list.

    :param member: the member to build the row for
    :param locale: "en" or "de"
    :returns: the member row template's values
    """
    names = get_display_names(member.record.get(ObjectAttribute.NAME), locale)
    return {
        "GROUP_MEMBER_NAME_FIRST": escape_html(names[0]),
        "GROUP_MEMBER_NAME_OTHER": escape_html(f"({', '.join(names[1:])})" if len(names) > 1 else ""),
        "GROUP_MEMBER_MAG": format_magnitude(str(member.record.get(ObjectAttribute.MAGNITUDE, ""))),
        "GROUP_MEMBER_SIZE": format_size(str(member.record.get(ObjectAttribute.SIZE, ""))),
    }


# --- double stars: an own pair takes its component, brightness and orbits from the WDS pair it references

def _wds_reference(obj: Object, site: SiteData) -> Object | None:
    return wds_reference(obj, site.references)


def get_pair_component(obj: Object, site: SiteData) -> dict[str, Any]:
    """The component of a pair: name, separation in arcseconds, position angle and year (each None when missing).

    :param obj: the pair to find the component of
    :param site: the shared row-building data (for the WDS reference lookup)
    :returns: name, separation, angle and year, each None when missing
    """
    source = _wds_reference(obj, site) or obj
    fields = [f.strip() for f in str(source.record.get(ObjectAttribute.COMPONENT, "")).split(",")]
    return {"name": fields[0] if fields and fields[0] else None,
            "separation": float(fields[1]) if len(fields) >= 2 and fields[1] else None,
            "angle": int(fields[2]) if len(fields) >= 3 and fields[2] else None,
            "year": int(fields[3]) if len(fields) == 4 and fields[3] else None}


def get_magnitude(obj: Object, site: SiteData) -> str:
    """A pair's own magnitude, or its WDS reference's when it has none of its own.

    :param obj: the pair to find the magnitude of
    :param site: the shared row-building data (for the WDS reference lookup)
    :returns: the magnitude, or "" when neither has one
    """
    own = str(obj.record.get(ObjectAttribute.MAGNITUDE, ""))
    if own:
        return own
    wds = _wds_reference(obj, site)
    return str(wds.record.get(ObjectAttribute.MAGNITUDE, "")) if wds is not None else ""


def get_coordinates(obj: Object, members: list[Object], site: SiteData) -> str:
    """An Object's own coordinates; a double star without its own takes them from its first member (as a
    group) or its WDS reference (as a pair).

    :param obj: the Object to find the coordinates of
    :param members: the Object's members, when it is a group
    :param site: the shared row-building data (for the WDS reference lookup)
    :returns: the coordinates, or "" when none are found
    """
    own = str(obj.record.get(ObjectAttribute.COORDINATES, ""))
    if own or T.DOUBLE_STAR not in obj.types or obj.rank != 0:
        return own
    if obj.is_group:
        return get_coordinates(members[0], [], site) if members else ""
    wds = _wds_reference(obj, site)
    return str(wds.record.get(ObjectAttribute.COORDINATES, "")) if wds is not None else ""


def entries_without_coordinates(entries: list[Entry], references: References | None) -> list[Entry]:
    """The entries whose row cannot show coordinates: the Global pages need them for every object but those of the
    Solar System (planets, comets, asteroids, the Moon), and a double star may take them from its WDS entry or,
    as a group, from its first pair.

    :param entries: the entries to check
    :param references: the catalogue cross-references, for WDS lookups
    :returns: the entries whose row would show no coordinates
    """
    site = SiteData(references=references)
    return [entry for entry in entries
            if T.SOLAR_SYSTEM not in entry.unit.types
            and format_coordinates(get_coordinates(
                entry.unit, sorted_members(entry, site) if entry.unit.is_group else [], site)) is None]


def sorted_members(entry: Entry, site: SiteData) -> list[Object]:
    """The members of a group, ordered by their component.

    :param entry: the group's entry
    :param site: the shared row-building data (for the WDS reference lookup)
    :returns: the members, in order
    """
    members = list(entry.members)
    if T.DOUBLE_STAR in entry.unit.types:
        members.sort(key=lambda m: natural_sort_key(get_pair_component(m, site)["name"] or ""))
    else:
        members.sort(key=lambda m: natural_sort_key(
            ",".join(localized_names(str(m.record.get(ObjectAttribute.NAME, "")), None))))
    return members


def members_share_a_name(group: Object, members: list[Object]) -> bool:
    """All members have the same names, and one of them is also a name of the group.

    :param group: the group
    :param members: the group's members
    :returns: whether the members' names coincide with each other and with one of the group's own
    """
    if not members:
        return False
    sets = [set(get_display_names(m.record.get(ObjectAttribute.NAME), None)) for m in members]
    common = set.intersection(*sets)
    group_names = set(get_display_names(group.record.get(ObjectAttribute.GROUP), None))
    return common == set.union(*sets) and bool(group_names & common)


def _double_star_components(row: dict[str, Any], pairs: list[Object], locale: str, site: SiteData,
                            equal_names: bool) -> None:
    """Fills in `row`'s DOUBLESTAR_COMPONENTS_HEAD and DOUBLESTAR_COMPONENTS: one entry per pair, with its
    component, magnitudes and, unless `equal_names` says every pair shares the same name, its own name(s).

    :param row: the row to fill in, in place
    :param pairs: the pairs to list (a group's members, or the pair itself)
    :param locale: "en" or "de"
    :param site: the shared row-building data (for the WDS reference lookup)
    :param equal_names: whether every pair has the same name, so no pair needs its own shown
    """
    row["DOUBLESTAR_COMPONENTS_HEAD"] = "Components:" if locale == EN else "Komponenten:"
    row["DOUBLESTAR_COMPONENTS"] = []
    name_sets = [set(get_display_names(p.record.get(ObjectAttribute.NAME), locale)) for p in pairs]
    common = set.intersection(*name_sets) if name_sets else set()
    for pair in pairs:
        component = get_pair_component(pair, site)
        primary, secondary = format_magnitude_pair(get_magnitude(pair, site))
        own_names = [n for n in get_display_names(pair.record.get(ObjectAttribute.NAME), locale) if n not in common]
        row["DOUBLESTAR_COMPONENTS"].append({
            "DOUBLESTAR_COMPONENT_NAME": escape_html(", ".join(own_names) if not equal_names else ""),
            "DOUBLESTAR_COMPONENT_COMP": escape_html(component["name"] or ""),
            "DOUBLESTAR_COMPONENT_MAG0": primary if primary else "-",
            "DOUBLESTAR_COMPONENT_MAG1": secondary if secondary else "-",
            "DOUBLESTAR_COMPONENT_DIST": escape_html(f'{component["separation"]}"' if component["separation"] else "-"),
            "DOUBLESTAR_COMPONENT_PA": escape_html(f"{component['angle']}°" if component["angle"] else "-"),
            "DOUBLESTAR_COMPONENT_YEAR": escape_html(f"{component['year']}" if component["year"] else "-"),
        })


def get_orbits(pair: Object, site: SiteData) -> list[OrbitSolution]:
    """The published orbital solutions of a pair: those of its WDS reference, or its own when it is itself
    a WDS-catalogue pair.

    :param pair: the pair to find the solutions of
    :param site: the shared row-building data (for the matched orbital solutions)
    :returns: the solutions, in file order
    """
    wds = _wds_reference(pair, site) or (pair if Path(pair.catalogue).stem.casefold() == "wds" else None)
    return list(site.orbits.get(id(wds), [])) if wds is not None else []


def existing_orbit_images(solutions: list[OrbitSolution], site: SiteData) -> list[str]:
    """The orbit diagrams that exist, as the pages link to them.

    :param solutions: the orbital solutions to find diagrams for
    :param site: the shared row-building data (for the image cache directory)
    :returns: the links of the diagrams that exist
    """
    images = []
    for solution in solutions:
        path = orbit_cache_path(site.data_dir, solution) if site.data_dir is not None else None
        if path is not None and path.is_file():
            images.append(f"{ORBITS_FOLDER}/{path.name}")
    return images


def _descriptions(entry: Entry, locale: str, site: SiteData,
                  orbit_solutions: list[OrbitSolution]) -> list[dict[str, Any]]:
    """Who observed what: the object's general information first, then the user, then the community observers.

    :param entry: the entry to describe
    :param locale: "en" or "de"
    :param site: the shared row-building data (observer names, instrument names, image caches)
    :param orbit_solutions: the object's orbital solutions, if any (see :func:`get_orbits`)
    :returns: one entry per observer group, each preceded by an "OBSERVER" header row unless the object is
        of the Solar System
    """
    groups: list[tuple[str | None, Sequence[FoundObservation | None]]] = []
    observations = _in_member_order(entry, site)
    info: list[FoundObservation | None] = [f for f in observations
                                           if f.observation.format is None and is_header(f.observation)]
    if not info and orbit_solutions:
        info = [None]  # nothing to say about the object, but its orbits are shown
    own = [f for f in observations if f.observation.format is None and not is_header(f.observation)]
    if info:
        groups.append((None, info))
    if own:
        groups.append((site.observer_name(site.owner_folder()), own))
    community: dict[str, list[FoundObservation | None]] = {}
    for found in observations:
        if found.observation.format is not None and found.observation.observer is not None:
            community.setdefault(found.observation.observer.id, []).append(found)
    for observer_id, found_list in community.items():
        groups.append((site.observer_name(observer_id), found_list))

    orbit_images = existing_orbit_images(orbit_solutions, site)
    labels = build_member_labels(entry, locale, site)
    remaining = sum(len(found_list) for _, found_list in groups)
    result: list[dict[str, Any]] = []
    solar = T.SOLAR_SYSTEM in entry.unit.types  # its rows are a plain sequence of observations, no observer headings
    for observer, found_list in groups:
        if not solar:
            result.append({"OBSERVER": escape_html(observer)})
        for found in found_list:
            label = labels.get(id(found.object)) if found is not None else None
            result.append(_description(found.observation if found else None, observer, remaining, locale, site,
                                       orbit_images, label))
            remaining -= 1
    return result


def _in_member_order(entry: Entry, site: SiteData) -> list[FoundObservation]:
    """The observations of a double star group: its own first, then those of its pairs, pair by pair.

    :param entry: the entry to order the observations of
    :param site: the shared row-building data (for the member order)
    :returns: the entry's observations, reordered when it is a double star group, unchanged otherwise
    """
    group = entry.unit
    if T.DOUBLE_STAR not in group.types or not group.is_group:
        return list(entry.observations)
    order = {id(m): index + 1 for index, m in enumerate(sorted_members(entry, site))}
    return sorted(entry.observations, key=lambda f: 0 if f.object is group else order.get(id(f.object), len(order) + 1))


def build_member_labels(entry: Entry, locale: str, site: SiteData) -> dict[int, str]:
    """What leads the description of an observation that a group took over from one of its pairs: the pair's name
    and component ("STF 60 (AB)"), or the component alone when all the pairs are known by a common name.

    :param entry: the group's entry
    :param locale: "en" or "de"
    :param site: the shared row-building data (for the member order and WDS reference lookups)
    :returns: id(member Object) -> its label, for the members that have one
    """
    group = entry.unit
    if T.DOUBLE_STAR not in group.types or not group.is_group:
        return {}
    members = sorted_members(entry, site)
    if not members:
        return {}
    name_sets = [set(get_display_names(m.record.get(ObjectAttribute.NAME), None)) for m in members]
    common = bool(set.intersection(*name_sets))
    labels: dict[int, str] = {}
    for member in members:
        component = get_pair_component(member, site)["name"]
        names = get_display_names(member.record.get(ObjectAttribute.NAME), locale)
        if not common and component and names:
            labels[id(member)] = f"{names[0]} ({component})"
        elif component:
            labels[id(member)] = component
    return labels


def _format_grade(grade: Grade) -> str:
    """A Grade as text: its range, or just the one number when it is not a range.

    :param grade: the grade to format
    :returns: the formatted grade
    """
    text = f"{grade.low:g}"
    if grade.high != grade.low:
        text += f"-{grade.high:g}"
    return text


def _description(observation: Observation | None, observer: str | None, remaining: int, locale: str,
                 site: SiteData, orbit_images: list[str], label: str | None = None) -> dict[str, Any]:
    """The values of one description row: the instrument and conditions line, the grade color, the text and
    the images. `observation` is None only for a made-up row that shows an object's orbit diagrams when it
    has no note of its own.

    :param observation: the observation to describe, or None for a made-up orbit-only row
    :param observer: the observer's name, or None for the object's general information
    :param remaining: how many more rows this observer group has left, including this one
    :param locale: "en" or "de"
    :param site: the shared row-building data (instrument names, image folders)
    :param orbit_images: the object's orbit diagrams, shown on the general-information row
    :param label: what leads the text, when the observation was taken over from another pair (see
        :func:`build_member_labels`)
    :returns: the description row template's values
    :raises ValueError: when `observation` has more than one visibility entry
    """
    english = locale == EN
    if observation is None:  # made up for an object with orbit diagrams but no note of its own
        images = list(orbit_images)
        text = "\n\n" if remaining > 1 and not images else ""
        return {"INFO": True, "HEAD": "", "GRADE": escape_html(COLOR_WHITE), "GRADE_TEXT": "",
                "DESCRIPTION": text.replace("\n", "<br>"), "IMAGES": images}
    record = observation.record
    head: list[str] = []
    optic = observation.optic
    if optic is not None and optic.type is OpticType.NAKED_EYE:
        head.append("naked eye" if english else "bl. Auge")
    elif optic is not None:
        head.append(optic.code if observation.project_only else site.optic_names.get(optic.code, optic.code))

    color, grade_text = COLOR_WHITE, ""
    if optic is not None and observation.visibility:
        if len(observation.visibility) > 1:
            raise ValueError("more than one element found for visibility")
        entry = observation.visibility[0]
        magnification = None
        if optic.type is OpticType.TELESCOPE and entry.magnification:
            magnification = f"{entry.magnification}x"
        if entry.filter:
            filter_text = f"[{entry.filter}]" if entry.filter == "OIII" else entry.filter
            magnification = f"{magnification} + {filter_text}" if magnification else filter_text
        if magnification:
            head.append(magnification)
        if isinstance(entry.result, Grade):
            grade_text = _format_grade(entry.result)
        elif entry.result is not None:
            style = GRADE_STYLE.get(entry.result)
            if style is not None:
                color, grade_text = style[0], style[1] if english else style[2]

    if record.get(ObservationAttribute.BORTLE):
        head.append(f"Bortle {record[ObservationAttribute.BORTLE]}")
    if record.get(ObservationAttribute.NELM):
        nelm_text = str(record[ObservationAttribute.NELM]).replace(".", HTML_MAGNITUDE)
        head.append(f"{'NELM' if english else 'FST'} {nelm_text}")
    if record.get(ObservationAttribute.SQM):
        head.append(f"SQM {record[ObservationAttribute.SQM]}")
    if record.get(ObservationAttribute.SQML):
        head.append(f"SQM-L {record[ObservationAttribute.SQML]}")
    if record.get(ObservationAttribute.SEEING):
        head.append(f"Seeing {record[ObservationAttribute.SEEING]}")

    owner_folder = site.owner_folder() if observation.format is None else (
        observation.observer.id if observation.observer else site.owner_folder())
    images = [f"{SKETCHES_FOLDER}/{owner_folder}/{name}" for name in observation.sketches]
    images += [f"{PHOTOGRAPHS_FOLDER}/{owner_folder}/{name}" for name in observation.photographs]
    images += [f"{IMAGES_FOLDER}/{name}" for name in observation.images]
    if observer is None:
        images += orbit_images

    text = build_description_text(record, locale, label)
    if head and text:
        text = f"\n{text}"
    if remaining > 1 and not images:
        text += "\n\n"
    if observer:
        text = escape_html(text)
    text = text.replace("\n", "<br>")
    return {"INFO": observer is None, "HEAD": ", ".join(head), "GRADE": escape_html(color),
            "GRADE_TEXT": escape_html(grade_text), "DESCRIPTION": text, "IMAGES": images}


def build_description_text(record: dict[str, Any], locale: str, label: str | None = None) -> str:
    """The description of the language, led by the Local conditions near the object when there are any.
    An observation that a group took over from one of its pairs (see :func:`build_member_labels`) is led by the
    pair too, after the conditions, shown once rather than duplicated around the pair - a deliberate choice.

    :param record: the observation's record
    :param locale: "en" or "de"
    :param label: what leads the text, when the observation was taken over from another pair
    :returns: the description text
    """
    text = str(record.get(
        ObservationAttribute.DESCRIPTION_EN if locale == EN else ObservationAttribute.DESCRIPTION_DE, ""
    ))
    if label:
        text = f"{label}: {text}" if text else label
    return _with_local_conditions(record, locale, text)


def _with_local_conditions(record: dict[str, Any], locale: str, text: str) -> str:
    """Prepends the Local conditions near the object (distinct from the observation's own site conditions)
    to `text`, when the record gives any.

    :param record: the observation's record
    :param locale: "en" or "de"
    :param text: the description text to prepend to
    :returns: `text`, with the local conditions prepended when there are any
    """
    nelm, sqml, seeing = (record.get(ObservationAttribute.NELM_LOCAL), record.get(ObservationAttribute.SQML_LOCAL),
                         record.get(ObservationAttribute.SEEING_LOCAL))
    if not (nelm or sqml or seeing):
        return text
    conditions = "Local conditions near the object: " if locale == EN else "Lokale Bedingungen in Objektnähe: "
    parts = []
    if nelm:
        nelm_text = str(nelm).replace(".", "m")
        parts.append(f"{'NELM' if locale == EN else 'FST'} {nelm_text}")
    if sqml:
        parts.append(f"SQM-L {sqml}")
    if seeing:
        parts.append(f"Seeing {seeing}")
    conditions += ", ".join(parts)
    if not text:
        return conditions
    return f"{conditions}\n\n{text}" if "\n\n" in text else f"{conditions}\n{text}"
