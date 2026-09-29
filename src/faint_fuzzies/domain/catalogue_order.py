"""The own catalogue's own record order, always applied before the file is written back: the Moon, the Sun,
the planets in their physical order, asteroids and comets first, then everything else by natural name order,
then a star (*, V* or C*) by natural name order too - except a double star pair that belongs to a Group of
this same catalogue, which instead sorts by that Group's own name and the pair's Component, so a system's
pairs stay together (and after their Group record, since its own name is always a prefix of theirs).
Meaningful for the own catalogue only: "Moon"/"Sun"/the planets and Group references are its own conventions -
the other catalogues are already sorted by their own converters.

A double-star attach-record (see importers.owner_double_stars) is not among catalogue.objects at all any
more - it sorts last, after every one of those, in the WDS's own file order (see
importers.attach.match_any_name): the WDS catalogue it is matched against the same way loading does.
"""
from faint_fuzzies.domain.catalogue import Catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType, split_names
from faint_fuzzies.domain.names import PAIR, component_of, has_component, is_star, kind_of
from faint_fuzzies.domain.sorting import natural_sort_key
from faint_fuzzies.importers.attach import Matcher, match_any_name

# German, matching the own catalogue's own naming - this order is only ever compared against names actually
# written in the (German-language) own catalogue.
_PLANETS = {"Merkur": 1, "Venus": 2, "Mars": 3, "Jupiter": 4, "Saturn": 5, "Uranus": 6, "Neptun": 7, "Pluto": 8}


def own_catalogue_order(catalogue: Catalogue, wds: Catalogue | None,
                        attach_records: list[dict]) -> list[dict]:
    """The own catalogue's records (catalogue.objects' and attach_records' together) in the own
    catalogue's own write-back order.

    :param catalogue: the own catalogue, loaded with double-star attach-records skipped (see
        domain.catalogue.load_catalogue's `skip`)
    :param wds: the WDS catalogue, to resolve each attach-record's position by; None sorts every
        attach-record last, in its original file order, when it is not available (e.g. not converted yet)
    :param attach_records: the own catalogue's raw double-star attach-records, in file order; empty when
        there are none
    :returns: every record, in the own catalogue's own order
    """
    collection = Collection([catalogue, *([wds] if wds is not None else [])])
    ordered = sorted(catalogue.objects, key=lambda obj: (is_star(obj), natural_sort_key(_sort_string(obj, collection))))
    records = [obj.record for obj in ordered]
    if not attach_records:
        return records
    if wds is None:
        return records + attach_records
    matcher = Matcher(collection)
    return records + sorted(attach_records, key=lambda record: _attach_record_position(record, matcher))


def _attach_record_position(record: dict, matcher: Matcher) -> tuple[int, int]:
    """Where an attach-record sorts among the others: by its matched WDS Object's file position, or last
    (after every matched one, in original file order) when it cannot be resolved at all."""
    name = record.get(ObjectAttribute.NAME, "")
    if not isinstance(name, str) or not name.strip():
        return (1, 0)
    component = str(record.get(ObjectAttribute.COMPONENT, "") or "").split(",", 1)[0].strip()
    target = match_any_name(matcher, split_names(name), component, "", 0, name, [])
    return (0, target.number) if target is not None else (1, 0)


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
