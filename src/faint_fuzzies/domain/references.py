"""References: direct links between Objects of different catalogues that stand for the same thing.

Objects are linked by a shared name. Group, pair and other Objects form separate kinds and only
link within their kind: a group links to groups, a pair (double star) to a pair with the same
Component, anything else by name alone. A group also references the groups whose members
reference its members, because groups are often named differently (a discoverer designation in
one catalogue, a Bayer name and the WDS id in another). References never exist within one
catalogue and are not chained.
"""
from collections import defaultdict
from pathlib import Path

from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType
from faint_fuzzies.domain.names import GROUP, PAIR, component_of, kind_of, names_of


def _share_a_type(objects: list[Object]) -> bool:
    """Whether two of the Objects have a type in common; an Object without types counts as sharing.

    :param objects: the objects to check
    :returns: whether any two of them share a type
    """
    for position, first in enumerate(objects):
        for second in objects[position + 1:]:
            if not first.types or not second.types or set(first.types) & set(second.types):
                return True
    return False


class References:
    """Computes and caches the References between the Objects of a Collection."""

    def __init__(self, collection: Collection):
        """:param collection: the collection to compute references within"""
        self._collection = collection
        self._cache: dict[int, list[Object]] = {}

    def of(self, obj: Object) -> list[Object]:
        """The Objects of the other catalogues that this Object references, in catalogue order. A double star
        pair combines its names by intersection rather than union (see _pair_matches): unlike a Group or an
        "other" Object, which may legitimately appear in several external catalogues under different names at
        once (a galaxy in both UGC and Herschel, say - both true, both kept), a pair has exactly one real
        identity in the WDS, so a name that is ambiguous on its own is resolved by requiring every other name
        that matched anything to agree, rather than keeping every candidate any name happened to find.

        :param obj: the object to find the references of
        :returns: its references, in catalogue order
        """
        cached = self._cache.get(id(obj))
        if cached is not None:
            return cached
        kind = kind_of(obj)
        if kind == PAIR:
            found = self._pair_matches(obj)
        else:
            found = {}
            for name in names_of(obj, kind):
                for other in self._collection.names.lookup(kind, name):
                    if other.rank != obj.rank:
                        found[id(other)] = other
            if kind == GROUP:
                for group in self._groups_through_members(obj):
                    found[id(group)] = group
        result = sorted(found.values(), key=lambda o: (o.rank, o.number))
        self._cache[id(obj)] = result
        return result

    def _pair_matches(self, obj: Object) -> dict[int, Object]:
        """A double star pair's references: for the WDS specifically, the intersection of what the pair's
        names individually match there (a name that matches nothing in the WDS is left out of the
        intersection rather than emptying it) - see `of` - since the WDS is the one external catalogue a
        pair's own data (coordinates, magnitude, separation) is borrowed from, so it needs exactly one match.
        Any other catalogue that happens to also have double star entries (SAC has some) is purely
        informational for a pair, like any reference of a non-double star Object, so those stay a plain union.
        A pair without a Component matches a pair without one too (both count as AB, see names.component_of).

        :param obj: the pair to find the references of
        :returns: id(Object) -> Object, its references
        """
        component = component_of(obj)
        wds_per_name: list[dict[int, Object]] = []
        found: dict[int, Object] = {}
        for name in obj.names:
            matches = {id(other): other for other in self._collection.names.lookup(PAIR, name)
                      if other.rank != obj.rank and component_of(other) == component}
            wds_matches = {i: o for i, o in matches.items() if Path(o.catalogue).stem.casefold() == "wds"}
            if wds_matches:
                wds_per_name.append(wds_matches)
            found.update({i: o for i, o in matches.items() if Path(o.catalogue).stem.casefold() != "wds"})
        if wds_per_name:
            common_ids = set(wds_per_name[0])
            for matches in wds_per_name[1:]:
                common_ids &= set(matches)
            combined = {i: other for matches in wds_per_name for i, other in matches.items()}
            found.update({i: combined[i] for i in common_ids})
        return found

    def resolved(self, obj: Object, key: str) -> str:
        """This Object's own value for a record attribute, or (when it has none) its WDS reference's -
        never any other catalogue's: the WDS is the only external catalogue trusted enough to fill a gap
        in the own catalogue's own data (see wds_reference). The own catalogue's double stars usually
        carry no COORDINATES or MAGNITUDE at all - that detail lives on the WDS pair they reference - so
        this is how a caller reads either attribute without caring that it came from there.

        :param obj: the object to resolve the attribute for
        :param key: the record attribute to resolve
        :returns: the resolved value, or "" when neither the object nor its WDS reference has one
        """
        value = obj.record.get(key)
        if value:
            return str(value)
        wds = wds_reference(obj, self)
        if wds is not None:
            value = wds.record.get(key)
            if value:
                return str(value)
        return ""

    def resolved_separation(self, obj: Object) -> str:
        """A double star's separation in arcseconds: the second part of COMPONENT ("letters,
        separation, position angle, year"). The own catalogue records only the letters, so this
        falls back to the WDS pair it references (never any other catalogue, see wds_reference) for
        the rest. The WDS writes -1 for an unknown separation (never a real value, since a separation
        can't be negative) - treated the same as a blank one, falling back the same way.

        :param obj: the double star to resolve the separation for
        :returns: the separation in arcseconds, or "" when neither the object nor its WDS reference has one
        """
        wds = wds_reference(obj, self)
        for candidate in (obj, wds) if wds is not None else (obj,):
            parts = str(candidate.record.get(ObjectAttribute.COMPONENT, "")).split(",")
            if len(parts) >= 2 and parts[1].strip():
                value = parts[1].strip()
                if float(value) >= 0:
                    return value
        return ""

    def _groups_through_members(self, group: Object) -> list[Object]:
        """The groups of other catalogues that contain a member referenced by a member of this group.

        :param group: the group to find other catalogues' groups for
        :returns: the other groups found
        """
        members = {id(m): m for name in group.groups for m in self._collection.members_named(group.rank, name)}
        found: dict[int, Object] = {}
        for member in members.values():
            for other_member in self.of(member):
                for name in other_member.groups:
                    for other_group in self._collection.groups_named(other_member.rank, name):
                        found[id(other_group)] = other_group
        return list(found.values())

    def ambiguities(self, objects: list[Object] | None = None) -> list[tuple[Object, str, list[Object]]]:
        """Objects that reference several Objects of one type in the same other catalogue.

        That usually means a duplicate or a too common name; all the links are still references.
        An object that a catalogue lists twice under different types (a historical quirk of
        some official catalogues, such as a cluster and its nebula) is not an ambiguity. `objects` limits the check
        to those Objects; the whole collection is much slower.

        :param objects: the objects to check; the whole collection when not given
        :returns: (object, catalogue name, the ambiguous references), one per ambiguity found
        """
        found = []
        for obj in self._collection.objects if objects is None else objects:
            by_catalogue: dict[str, list[Object]] = defaultdict(list)
            for other in self.of(obj):
                by_catalogue[other.catalogue].append(other)
            found.extend((obj, name, others) for name, others in by_catalogue.items() if _share_a_type(others))
        return found


def wds_reference(obj: Object, references: References | None) -> Object | None:
    """The WDS pair an own-catalogue double star pair references, or None: it has none, is itself a Group, is
    not a double star, belongs to another catalogue, is marked DISABLE_WDS, or `references` is not given at
    all. Under `--data-dir`, this never actually returns anything: the only double star Object that still
    exists at rank 0 there is a DISABLE_WDS one (every other one is an attach-record instead, see
    CONTEXT.md "Own catalogue") - and that is exactly what the DISABLE_WDS check here excludes. It still
    matters for a bare `--catalogue` file, where no such split happens and a plain double star Object may
    genuinely reference the WDS the old way; used by the website, which borrows the WDS pair's component,
    brightness and orbits for that case.

    :param obj: the double star pair to find the WDS reference of
    :param references: the references to look through
    :returns: the WDS pair, or None
    """
    if (references is None or obj.rank != 0 or obj.is_group or ObjectType.DOUBLE_STAR not in obj.types
            or obj.record.get(ObjectAttribute.DISABLE_WDS)):
        return None
    for reference in references.of(obj):
        if Path(reference.catalogue).stem.casefold() == "wds":
            return reference
    return None
