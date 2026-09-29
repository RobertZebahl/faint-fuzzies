"""Lists: what the user and other observers publish, grouped by the object observed.

A list has contributors (the user, and the observers of certain import formats), an object rule and an
observation rule. Its entries carry the observations that qualify, the ratings of the observers, and
the sublists the entry belongs to. The rules are:

* **global**: objects of the first catalogue (the own catalogue) with public observations of the user and of
  the Global observers.
* **project-double-stars**: double stars, one entry per system, with the observations of the user and of the
  observers of the Double Stars formats; `DISABLE_PROJECT_DOUBLE_STARS` leaves an object out.
* **project-deep-sky-with-binoculars**: deep sky objects of the first catalogue with observations made with
  binoculars or the naked eye; stars, double stars, novae, supernovae and non-existent objects are left out.

The pairs of a group belong to the group's entry, and the same system in two catalogues is one entry, kept
under the object of the earlier catalogue.

An entry is published only with at least one valid observation, from anyone; a Header is none. The global list
also publishes an object marked PUBLISH_WITHOUT_OBSERVATION without one.
"""
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.model import COORDINATES_FORMAT, Object, ObjectAttribute
from faint_fuzzies.domain.model import ObjectType as T
from faint_fuzzies.domain.names import PAIR, kind_of
from faint_fuzzies.domain.observation import FoundObservation, Observation, OpticType, is_header
from faint_fuzzies.domain.observer import OWN_ID, Observers, Scope
from faint_fuzzies.domain.references import References, wds_reference
from faint_fuzzies.domain.sorting import natural_sort_key

DEEP_SKY_EXCLUDED = {T.SOLAR_SYSTEM, T.STAR, T.DOUBLE_STAR, T.NOVA, T.SUPERNOVA, T.NON_EXISTENT}
DEEP_SKY_EXCEPTIONS = ("Messier 40",)  # a double star that observers treat as deep sky


@dataclass
class Entry:
    """One entry of a built list: an Object (or the group that stands for its system) with the
    observations, ratings and sublist memberships that qualified it.

    :ivar unit: the object that stands for the entry: a group, or a single object
    :ivar observations: the qualifying observations
    :ivar header: the user's notes without an instrument
    :ivar rated_only: observations left out of the entry, but whose rating still counts
    :ivar ratings: observer id -> highest rating
    :ivar sublists: the names of the sublists this entry belongs to
    :ivar members: the pairs of a group
    :ivar coordinates: right ascension in hours, declination in degrees
    :ivar contributors: the raw objects whose observations feed the entry
    :ivar flagged: a contributor is marked to be published without observation (only where the list allows it)
    :ivar references: the objects of other catalogues the unit references
    :ivar has_orbit: a pair of the system (or the same pair in another catalogue) has an orbit diagram
    """
    unit: Object
    observations: list[FoundObservation] = field(default_factory=list)
    header: list[FoundObservation] = field(default_factory=list)
    rated_only: list[FoundObservation] = field(default_factory=list)
    ratings: dict[str, int] = field(default_factory=dict)
    sublists: list[str] = field(default_factory=list)
    members: list[Object] = field(default_factory=list)
    coordinates: tuple[float, float] | None = None
    contributors: list[Object] = field(default_factory=list)
    flagged: bool = False
    references: list[Object] = field(default_factory=list)
    has_orbit: bool = False

    @property
    def catalogue(self) -> str:
        """The unit's catalogue."""
        return self.unit.catalogue

    @property
    def average_rating(self) -> float:
        """The average of `ratings`, 0.0 when there are none."""
        return sum(self.ratings.values()) / len(self.ratings) if self.ratings else 0.0

    @property
    def rounded_rating(self) -> int:
        """The average rating rounded up, which is what the best-of and recommendation lists use."""
        return math.ceil(self.average_rating)


@dataclass(frozen=True)
class ListDefinition:
    """What defines one of the lists in LISTS: who contributes, which objects and observations qualify,
    and the sublists it offers.

    :ivar name: the list's own name
    :ivar formats: import formats whose observers contribute, besides the user
    :ivar rating_formats: formats whose ratings count in this list
    :ivar first_catalogue_only: whether only the first (own) catalogue's objects take part
    :ivar roll_up: whether the pairs of a group are entered under the group
    :ivar header_notes: whether the user's public notes without an instrument are a header, not observations
    :ivar publish_flagged: whether an object marked PUBLISH_WITHOUT_OBSERVATION is listed even without any
        observation
    :ivar sort_by_position: whether entries sort by sky position rather than name
    :ivar accepts_object: whether an object may form an entry
    :ivar accepts_observation: whether an observation counts, beyond the contributor checks
    :ivar user_rating: the user's stored rating of an object, 0 when none
    :ivar sublists: the list's sublists, by name
    """
    name: str
    formats: frozenset[str]
    rating_formats: frozenset[str]
    first_catalogue_only: bool
    roll_up: bool
    header_notes: bool
    publish_flagged: bool
    sort_by_position: bool
    accepts_object: Callable[[Object], bool]
    accepts_observation: Callable[[Observation], bool]
    user_rating: Callable[[Object], int]
    sublists: dict[str, Callable[[Entry], bool]]


@dataclass
class ListResult:
    """The result of building a list: its entries and their aggregate statistics, overall and per sublist.

    :ivar definition: the list definition this was built from
    :ivar entries: the published entries
    :ivar statistics: the overall statistics, as `_statistics` builds them
    :ivar sublist_statistics: the same statistics, per sublist name
    """
    definition: ListDefinition
    entries: list[Entry]
    statistics: dict
    sublist_statistics: dict[str, dict]


def _is_double_star(obj: Object) -> bool:
    return T.DOUBLE_STAR in obj.types


def _has_type(code: T) -> Callable[[Entry], bool]:
    return lambda e: code in e.unit.types


def _rating_at_least(minimum: int) -> Callable[[Entry], bool]:
    return lambda e: e.rounded_rating >= minimum


def _right_ascension(low: int, high: int) -> Callable[[Entry], bool]:
    return lambda e: e.coordinates is not None and low <= e.coordinates[0] < high


def _has_files(method: str, attribute: str) -> Callable[[Entry], bool]:
    return lambda e: any(f.observation.method == method and getattr(f.observation, attribute) for f in e.observations)


def _tag(letter: str) -> Callable[[Entry], bool]:
    """The list tag (B, M, C) is kept on the system or on any of its pairs."""
    return lambda e: any(letter in str(o.record.get(ObjectAttribute.PROJECT_DOUBLE_STARS_LISTS, ""))
                         for o in [e.unit, *e.members])


def _has_orbit(entry: Entry) -> bool:
    """An orbit diagram for the system, and at least one observation to show it with."""
    return entry.has_orbit and bool(entry.observations)


def _has_name_starting(prefix: str) -> Callable[[Entry], bool]:
    return lambda e: any(n.startswith(prefix) for n in e.unit.names)


def _stored_rating(attribute: str) -> Callable[[Object], int]:
    def rating(obj: Object) -> int:
        value = obj.record.get(attribute, 0)
        return value if isinstance(value, int) and 0 < value <= 3 else 0
    return rating


def _accepts_double_star(unit: Object) -> bool:
    return _is_double_star(unit) and not unit.record.get(ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS)


def _accepts_deep_sky(obj: Object) -> bool:
    if any(name in obj.names for name in DEEP_SKY_EXCEPTIONS):
        return True
    return not obj.is_group and not DEEP_SKY_EXCLUDED.intersection(obj.types)


def _without_telescope(observation: Observation) -> bool:
    return observation.optic is None or observation.optic.type is not OpticType.TELESCOPE


_RIGHT_ASCENSION_BANDS = {f"ra-{low:02d}-{low + 6:02d}": _right_ascension(low, low + 6) for low in (0, 6, 12, 18)}
_TYPE_SUBLISTS = {
    "asterisms": _has_type(T.ASTERISM), "open-clusters": _has_type(T.OPEN_CLUSTER),
    "globular-clusters": _has_type(T.GLOBULAR_CLUSTER), "planetary-nebulae": _has_type(T.PLANETARY_NEBULA),
    "bright-nebulae": _has_type(T.BRIGHT_NEBULA), "dark-nebulae": _has_type(T.DARK_NEBULA),
    "galaxies": _has_type(T.GALAXY),
}


# Global's sublists by Object type, and the categories the Statistics page uses for a private-only
# breakdown of the same shape (see ui/statistics.py). Name -> the type(s) that put an Object in it; most
# are a single type, `sublist_title` turns the name into the human-readable label used for display, and
# `OBJECT_TYPE_SUBLISTS` below turns it into the actual Object -> bool rule. Object-based, unlike
# _TYPE_SUBLISTS above, so both places can apply it directly to an Object without needing a whole Entry.
_TYPE_SUBLIST_TYPES: dict[str, tuple[T, ...]] = {
    "asterisms": (T.ASTERISM,), "open-clusters": (T.OPEN_CLUSTER,),
    "globular-clusters": (T.GLOBULAR_CLUSTER,), "planetary-nebulae": (T.PLANETARY_NEBULA,),
    "bright-nebulae": (T.BRIGHT_NEBULA,), "dark-nebulae": (T.DARK_NEBULA,), "galaxies": (T.GALAXY,),
    "galaxy-groups": (T.GALAXY_GROUP,), "double-stars": (T.DOUBLE_STAR,), "comets": (T.COMET,),
    "asteroids": (T.ASTEROID,), "solar-system": (T.SOLAR_SYSTEM,),
    "stars": (T.STAR, T.VARIABLE_STAR, T.CARBON_STAR), "novae-supernovae": (T.NOVA, T.SUPERNOVA),
}


def _has_any_type(codes: tuple[T, ...]) -> Callable[[Object], bool]:
    return lambda o: bool(set(codes).intersection(o.types))


OBJECT_TYPE_SUBLISTS: dict[str, Callable[[Object], bool]] = {
    name: _has_any_type(codes) for name, codes in _TYPE_SUBLIST_TYPES.items()
}
# the one category that isn't just "any of these types": sun, moon and the planets, i.e. solar system
# minus comets and asteroids, which get their own sublists above
OBJECT_TYPE_SUBLISTS["solar-system"] = (
    lambda o: T.SOLAR_SYSTEM in o.types and T.COMET not in o.types and T.ASTEROID not in o.types)


def sublist_title(name: str) -> str:
    """A sublist name (as used by --sublist and in JSON output) as a human-readable label, e.g.
    "galaxy-groups" -> "Galaxy Groups". Display only - the name itself stays the stable identifier.

    :param name: the sublist name
    :returns: the human-readable label
    """
    title = name.replace("-", " ").title()
    return f"{title} (Sun, Moon, Planets)" if name == "solar-system" else title


_ENUM_ORDER: dict[T, int] = {code: index for index, code in enumerate(T)}
_OTHERS_SORT_KEY = len(_ENUM_ORDER)  # "others" names no type of its own, so it always sorts last
# solar system objects lead, ahead of even where their own type falls in the enum - asteroids and comets
# right after, since they're conceptually part of the same "things in our solar system" group
_SORT_KEY_OVERRIDES: dict[str, int] = {"solar-system": -3, "asteroids": -2, "comets": -1}


def sublist_sort_key(name: str) -> int:
    """Where an OBJECT_TYPE_SUBLISTS category belongs in display order - solar system, asteroids and
    comets first (see _SORT_KEY_OVERRIDES), then everything else in ObjectType's own declaration order
    (stars before deep sky objects, in the same order the enum lists their types). A category of several
    types (e.g. "stars") sorts by the earliest of them; "others" names no type of its own and sorts last.

    :param name: the category name
    :returns: its sort key
    """
    if name in _SORT_KEY_OVERRIDES:
        return _SORT_KEY_OVERRIDES[name]
    codes = _TYPE_SUBLIST_TYPES.get(name)
    return min(_ENUM_ORDER[code] for code in codes) if codes else _OTHERS_SORT_KEY


def is_uncategorized(obj: Object) -> bool:
    """An Object that OBJECT_TYPE_SUBLISTS matches nowhere - Global's "others" sublist, and the same
    rule the private breakdown uses for its own "others" row.

    :param obj: the object to check
    :returns: whether it matches no OBJECT_TYPE_SUBLISTS category
    """
    return not any(rule(obj) for rule in OBJECT_TYPE_SUBLISTS.values())


def _on_unit(rule: Callable[[Object], bool]) -> Callable[[Entry], bool]:
    return lambda e: rule(e.unit)


# The lists of the website beyond the Global sublists by Object type above: the website's own menu pages,
# so that every page can show the size of every list. Named after their page. An Object's names
# and groups are matched whole, ignoring case.
RING_GALAXIES = ("NGC2685", "NGC2859", "NGC3718", "UGC6614")  # a fixed list
MESSIER_44_GALAXIES = ("NGC2624", "NGC2625", "NGC2637", "NGC2643", "NGC2647", "UGC4526")  # also fixed
HERSCHEL_NAME = r"H\d+\.\d+(?:\.\d+)?"


def _matches(pattern: str, texts: tuple[str, ...]) -> bool:
    return any(re.fullmatch(pattern, text, re.IGNORECASE) for text in texts)


def _named(pattern: str, *types: T) -> Callable[[Object], bool]:
    return lambda o: _matches(pattern, o.names) and (not types or bool(set(types).intersection(o.types)))


def _has_public_sketch(entry: Entry) -> bool:
    return any(found.observation.sketches for found in entry.observations)


def _is_red_star(obj: Object) -> bool:
    return T.STAR in obj.types and (T.CARBON_STAR in obj.types or bool(obj.record.get(ObjectAttribute.RED_STARS_LIST)))


def _is_herschel(obj: Object) -> bool:
    return Path(obj.catalogue).stem.casefold() == "herschel"


def _herschel_400(entry: Entry) -> bool:
    return any(_is_herschel(r) and "400" in r.groups for r in entry.references)


def herschel_names_without_reference(collection: Collection, references: References) -> list[tuple[Object, str]]:
    """The Objects of the own catalogue that carry a Herschel name (H1.1) but reference no Object of the Herschel
    catalogue, each with that name: the name is mistyped or missing there. Herschel 400 leaves such an Object out
    without a word, since it needs the reference; Herschel 2500 keeps it. Nothing is reported when no Herschel
    catalogue is loaded.

    :param collection: the collection to check
    :param references: the references to check against
    :returns: (object, Herschel name), one per Object with no reference to the Herschel catalogue
    """
    if not any(Path(c.name).stem.casefold() == "herschel" for c in collection.catalogues):
        return []
    found = []
    for obj in collection.objects:
        if obj.rank != 0:
            continue
        names = [n for n in obj.names + obj.groups if re.fullmatch(HERSCHEL_NAME, n, re.IGNORECASE)]
        if names and not any(_is_herschel(r) for r in references.of(obj)):
            found.append((obj, names[0]))
    return found


_arp_galaxy = _named(r"Arp\d+", T.GALAXY)
_arp_group = lambda o: o.is_group and _matches(r"Arp\d+", o.groups) and T.GALAXY_GROUP in o.types

WEBSITE_SUBLISTS: dict[str, Callable[[Entry], bool]] = {
    "complete-object-list": _on_unit(lambda o: T.SOLAR_SYSTEM not in o.types),
    "galaxies-and-groups": _on_unit(_has_any_type((T.GALAXY, T.GALAXY_GROUP, T.GALAXY_CLUSTER))),
    "red-stars": _on_unit(_is_red_star),
    "berkeley-clusters": _on_unit(_named(r"Berkeley \d+", T.OPEN_CLUSTER)),
    "king-clusters": _on_unit(_named(r"King \d+", T.OPEN_CLUSTER)),
    "abell-planetary-nebulae": _on_unit(_named(r"Abell \d+", T.PLANETARY_NEBULA)),
    "local-group": _on_unit(lambda o: T.GALAXY in o.types and _matches(r"Local Group", o.groups)),
    "hickson-groups": _on_unit(lambda o: o.is_group and _matches(r"Hickson \d+", o.groups)
                                         and T.GALAXY_GROUP in o.types),
    "arp-galaxies": _on_unit(lambda o: _arp_galaxy(o) or _arp_group(o)),
    "ring-galaxies": _on_unit(lambda o: T.GALAXY in o.types and any(_matches(n, o.names) for n in RING_GALAXIES)),
    "thin-galaxies": _on_unit(lambda o: T.GALAXY in o.types and (o.size_ratio or 0) >= 5),
    "superthin-galaxies": _on_unit(lambda o: T.GALAXY in o.types and (o.size_ratio or 0) >= 7),
    "galaxies-in-messier-44": _on_unit(lambda o: any(_matches(n, o.names) for n in MESSIER_44_GALAXIES)),
    "messier": _on_unit(lambda o: not o.is_group and _named(r"Messier \d+")(o)),
    "herschel-400": lambda e: (_matches(HERSCHEL_NAME, e.unit.names + e.unit.groups) and _herschel_400(e)),
    "herschel-2500": _on_unit(lambda o: _matches(HERSCHEL_NAME, o.names + o.groups)),
    "sketches-gallery": _has_public_sketch,
    "sketches-deepsky": lambda e: (_has_public_sketch(e) and T.SOLAR_SYSTEM not in e.unit.types
                                   and T.COMET not in e.unit.types),
    "sketches-comets": lambda e: _has_public_sketch(e) and T.COMET in e.unit.types,
    "sketches-planets": lambda e: _has_public_sketch(e) and T.PLANET in e.unit.types,
    "sketches-moon": lambda e: _has_public_sketch(e) and "Moon" in e.unit.names,
    "sketches-sun": lambda e: _has_public_sketch(e) and "Sun" in e.unit.names,
}


def website_count(name: str, entries: list[Entry]) -> int:
    """The number the website's menu shows beside a list: its entries, except that the Messier list
    counts distinct Messier names (two objects with the same one, such as the nebula and the cluster of
    Messier 16, count once) and the gallery counts the different sketches, not the objects.

    :param name: the list or sublist name
    :param entries: the entries to count among
    :returns: the count to show
    """
    members = [entry for entry in entries if name in entry.sublists]
    if name == "messier":
        return len({n for e in members for n in e.unit.names if re.fullmatch(r"Messier \d+", n)})
    if name == "sketches-gallery":
        return len({sketch for e in members for found in e.observations for sketch in found.observation.sketches})
    return len(members)


LISTS = {
    "global": ListDefinition(
        "global", frozenset(), frozenset(), True, True, False, True, False,
        lambda o: True, lambda o: True, lambda o: 0,
        {"complete": lambda e: True,
         **{name: _on_unit(rule) for name, rule in OBJECT_TYPE_SUBLISTS.items()},
         "others": _on_unit(is_uncategorized), **WEBSITE_SUBLISTS}),
    "project-double-stars": ListDefinition(
        "project-double-stars",
        frozenset({"project-double-stars-visual", "project-double-stars-photographic", "global"}),
        frozenset({"project-double-stars-visual", "project-double-stars-photographic"}), False, True, True, False, True,
        _accepts_double_star, lambda o: True, _stored_rating(ObjectAttribute.RATING),
        {"complete": lambda e: True, "binoculars": _tag("B"), "best-of": _rating_at_least(3),
         "recommendations": _rating_at_least(1), "multiples": _tag("M"), "colored": _tag("C"),
         **_RIGHT_ASCENSION_BANDS, "sketches": _has_files("visual", "sketches"),
         "photographs": _has_files("photographic", "photographs"), "orbits": _has_orbit}),
    "project-deep-sky-with-binoculars": ListDefinition(
        "project-deep-sky-with-binoculars", frozenset({"project-deep-sky-with-binoculars", "global"}),
        frozenset({"project-deep-sky-with-binoculars", "global"}), True, False, True, False, False,
        _accepts_deep_sky, _without_telescope, _stored_rating(ObjectAttribute.PROJECT_DEEP_SKY_WITH_BINOCULARS_RATING),
        {"complete": lambda e: True, **_TYPE_SUBLISTS, "messier": _has_name_starting("Messier "),
         "best-of": _rating_at_least(3), "recommendations": _rating_at_least(1),
         "sketches": _has_files("visual", "sketches"), **_RIGHT_ASCENSION_BANDS}),
}


def build_list(definition: ListDefinition, collection: Collection, references: References,
               observers: Observers | None = None, orbit_pairs: frozenset[int] = frozenset()) -> ListResult:
    """Builds a list from a collection: which objects and observations qualify, grouped into entries,
    rated and sorted into sublists.

    :param definition: the list to build
    :param collection: the collection to build it from
    :param references: the collection's cross-references
    :param observers: the observers, to resolve ids and scopes
    :param orbit_pairs: the ids (`id()`) of the pairs that have an orbit diagram, for the sublist "orbits"
    :returns: the built list
    """
    ranks = 1 if definition.first_catalogue_only else len(collection.catalogues)  # the catalogues that take part
    drafts: dict[int, Entry] = {}
    for obj in collection.objects:
        if obj.rank >= ranks:
            break  # the objects are in the order of their catalogues
        observations = [o for o in obj.all_observations if _contributes(definition, o, observers)]
        flagged = definition.publish_flagged and obj.publish_without_observation
        if not observations and not flagged:
            continue
        unit = _group_of(collection, obj) if definition.roll_up else None
        unit = unit or obj
        if not definition.accepts_object(unit) or (unit is not obj
                                                    and obj.record.get(ObjectAttribute.DISABLE_PROJECT_DOUBLE_STARS)):
            continue
        canonical = _canonical(unit, references, ranks)
        entry = drafts.setdefault(id(canonical), Entry(canonical))
        entry.contributors.append(obj)
        entry.flagged = entry.flagged or flagged
        for observation in observations:
            found = FoundObservation(observation, obj)
            if _is_header(definition, observation):
                entry.header.append(found)
            elif definition.accepts_observation(observation):
                entry.observations.append(found)
            elif observation.rating:
                entry.rated_only.append(found)  # a rating recommends the object, whatever instrument was used

    # published: at least one valid observation, from anyone (a Header is none), or the mark that overrides this
    entries = [e for e in drafts.values() if counted_observations(e) or e.flagged]
    for entry in entries:
        _fill(entry, definition, collection, references, observers, orbit_pairs)
    entries.sort(key=(lambda e: _position_key(e)) if definition.sort_by_position
                 else (lambda e: natural_sort_key(_order_text(e.unit))))
    result = ListResult(definition, entries, _statistics(entries, observers), {})
    for name, rule in definition.sublists.items():
        members = [e for e in entries if rule(e)]
        for entry in members:
            entry.sublists.append(name)
        result.sublist_statistics[name] = _statistics(members, observers)
    return result


def _contributes(definition: ListDefinition, observation: Observation, observers: Observers | None) -> bool:
    if not observation.public:
        return False
    if observation.format is None:
        return True  # the owner's own observations always contribute
    if definition.name == "global":
        # Global's contributors are the owner (above) and whoever has scope GLOBAL, through any format;
        # it does not use `definition.formats` at all.
        observer = observers.get(observation.observer.id) if observers and observation.observer else None
        return observer is not None and observer.scope is Scope.GLOBAL
    return observation.format in definition.formats


def _is_header(definition: ListDefinition, observation: Observation) -> bool:
    return definition.header_notes and is_header(observation)


def _group_of(collection: Collection, obj: Object) -> Object | None:
    """The group of the same catalogue that a pair belongs to, when there is exactly one."""
    if obj.is_group or not obj.groups or kind_of(obj) != PAIR:
        return None
    found = {id(g): g for name in obj.groups for g in collection.groups_named(obj.rank, name)}
    return next(iter(found.values())) if len(found) == 1 else None


def _canonical(unit: Object, references: References, ranks: int) -> Object:
    """The same system in several catalogues is one entry, kept under the object of the earliest catalogue."""
    same_kind = [r for r in references.of(unit) if kind_of(r) == kind_of(unit) and r.rank < ranks]
    return min([unit, *same_kind], key=lambda o: (o.rank, o.number))


def _fill(entry: Entry, definition: ListDefinition, collection: Collection, references: References,
         observers: Observers | None, orbit_pairs: frozenset[int]) -> None:
    unit = entry.unit
    entry.members = collection.members_of(unit)
    # the user's rating of a system is kept on the system or on its pairs; the highest one counts
    stored = max(definition.user_rating(o) for o in [unit, *entry.members])
    if stored:
        entry.ratings[observers.owner_id() if observers else OWN_ID] = stored
    for found in [*entry.observations, *entry.rated_only]:
        observation = found.observation
        if observation.rating and observation.observer and observation.format in definition.rating_formats:
            key = observation.observer.id
            entry.ratings[key] = max(entry.ratings.get(key, 0), observation.rating)
    entry.coordinates = get_coordinates(unit, entry.members, references)
    entry.references = list(references.of(unit))
    if orbit_pairs:
        parts = [unit, *entry.members]
        entry.has_orbit = any(id(o) in orbit_pairs
                               for o in [*parts, *(r for part in parts for r in references.of(part))])


def get_coordinates(unit: Object, members: list[Object], references: References) -> tuple[float, float] | None:
    """A unit's own coordinates, a member's (as a group), or, for a double star, its WDS reference's -
    never any other catalogue's (see references.wds_reference): the WDS is the only external catalogue
    trusted enough to fill a gap in the own catalogue's own data."""
    candidates = [unit, *members]
    candidates += [wds for c in list(candidates) if (wds := wds_reference(c, references)) is not None]
    for candidate in candidates:
        match = COORDINATES_FORMAT.fullmatch(str(candidate.record.get(ObjectAttribute.COORDINATES, "")))
        if match:
            ra_h, ra_m, ra_s, sign, dec_d, dec_m, dec_s = match.groups()
            declination = int(dec_d) + int(dec_m) / 60 + float(dec_s) / 3600
            return int(ra_h) + int(ra_m) / 60 + float(ra_s) / 3600, -declination if sign == "-" else declination
    return None


PLANETS = ("Merkur", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptun", "Pluto")  # in the order of the sky


def _order_text(obj: Object) -> str:
    """What an Object is ordered by: its first name, except that the Solar System comes first, as in the previous
    tool: the Moon, the Sun, the planets in their order, asteroids and comets (each by name)."""
    if "Moon" in obj.names:
        return "0 0 " + obj.label
    if "Sun" in obj.names:
        return "0 1 " + obj.label
    if T.PLANET in obj.types:
        number = PLANETS.index(obj.label) + 1 if obj.label in PLANETS else len(PLANETS) + 1
        return f"0 2 {number}{obj.label}"
    if T.ASTEROID in obj.types:
        return "0 3 " + obj.label
    if T.COMET in obj.types:
        return "0 4 " + obj.label
    return obj.label


def _position_key(entry: Entry):
    return ((0, entry.coordinates, natural_sort_key(entry.unit.label)) if entry.coordinates
            else (1, (0.0, 0.0), natural_sort_key(entry.unit.label)))


def counted_observations(entry: Entry) -> list[FoundObservation]:
    """The observations of an entry that count in the statistics: all but the Header, which is general information
    about the Object and never reports an observing session."""
    return [found for found in entry.observations if not is_header(found.observation)]


def _statistics(entries: list[Entry], observers: Observers | None) -> dict:
    visual = photographic = sketches = photographs = 0
    people: dict[str, dict[str, str]] = {}
    for entry in entries:
        for found in counted_observations(entry):
            observation = found.observation
            key = observation.observer.id if observation.observer else (observers.owner_id() if observers else OWN_ID)
            person = observation.observer or (observers.owner if observers else None)
            people[key] = {"id": key, "name": person.name if person else key,
                           "sort": f"{person.surname} {person.firstname}" if person else key}
            if observation.method == "photographic":
                photographic += 1
                photographs += len(observation.photographs)
            else:
                visual += 1
                sketches += len(observation.sketches)
    ordered = sorted(people.values(), key=lambda p: p["sort"].casefold())
    return {"objects": len(entries), "visual_observations": visual, "photographic_observations": photographic,
            "sketches": sketches, "photographs": photographs,
            "observers": [{"id": p["id"], "name": p["name"]} for p in ordered]}
