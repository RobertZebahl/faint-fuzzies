"""The own catalogue's own object order, always applied before the file is written back: the Moon, the Sun,
the planets in their physical order, asteroids and comets first, then everything else by natural name order -
except a double star pair that belongs to a Group of this same catalogue, which instead sorts by that Group's
own name and the pair's Component, so a system's pairs stay together (and after their Group record, since its
own name is always a prefix of theirs). Meaningful for the own catalogue only: "Moon"/"Sun"/the planets and
Group references are its own conventions - the other catalogues are already sorted by their own converters.
"""
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.model import Object, ObjectType
from faint_fuzzies.domain.names import PAIR, component_of, has_component, kind_of
from faint_fuzzies.domain.sorting import natural_sort_key

# German, matching the own catalogue's own naming - this order is only ever compared against names actually
# written in the (German-language) own catalogue.
_PLANETS = {"Merkur": 1, "Venus": 2, "Mars": 3, "Jupiter": 4, "Saturn": 5, "Uranus": 6, "Neptun": 7, "Pluto": 8}


def own_catalogue_order(catalogue) -> list[Object]:
    """Reorders a catalogue's objects into the own catalogue's own order.

    :param catalogue: the catalogue to reorder (a Catalogue; the own catalogue is the only sensible input)
    :returns: catalogue.objects, reordered
    """
    collection = Collection([catalogue])
    return sorted(catalogue.objects, key=lambda obj: natural_sort_key(_sort_string(obj, collection)))


def _sort_string(obj: Object, collection: Collection) -> str:
    """The string `obj` sorts by: a double star pair of this collection's own-catalogue Group sorts after
    that Group's own name; the Moon, Sun, planets, asteroids and comets come first, each in their own
    order; everything else sorts by its own label.

    :param obj: the object to build a sort string for
    :param collection: the collection `obj` belongs to, to look up its Group
    :returns: the string to pass through natural_sort_key
    """
    label = obj.label
    if kind_of(obj) == PAIR and obj.groups:
        group = next((g for name in obj.groups for g in collection.groups_named(0, name)), None)
        if group is not None:
            return group.label + (component_of(obj) if has_component(obj) else "")
    if "Moon" in obj.names:
        return f"0 0 {label}"
    if "Sun" in obj.names:
        return f"0 1 {label}"
    if ObjectType.PLANET in obj.types and label in _PLANETS:
        return f"0 2 {_PLANETS[label]}{label}"
    if ObjectType.ASTEROID in obj.types:
        return f"0 3 {label}"
    if ObjectType.COMET in obj.types:
        return f"0 4 {label}"
    return label
