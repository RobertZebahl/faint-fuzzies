"""The Objects of all the catalogues loaded together, in one place to query."""
from collections import defaultdict
from collections.abc import Callable, Sequence

from faint_fuzzies.domain.catalogue import Catalogue
from faint_fuzzies.domain.model import Object, ObjectType
from faint_fuzzies.domain.names import NameIndex, full_key, indexed_forms


class Collection:
    """Catalogues loaded together, in search order: the own catalogue first.

    Every Object of them is in `objects`, in the order of the catalogues and then of their records. Each Object
    knows its catalogue and the rank of that catalogue, which is also the order of preference where catalogues
    overlap. An Object belongs to one Collection. Groups and their members always belong to one catalogue, so
    they are looked up by catalogue rank and name.
    """

    def __init__(self, catalogues: Sequence[Catalogue], on_progress: Callable[[int, int], None] | None = None):
        """:param catalogues: the catalogues to collect, in search order (the own catalogue first)
        :param on_progress: given (objects indexed so far, the total), reports the progress of building
            the name index - by far the dominant cost of this for a large collection; see NameIndex
        """
        self.catalogues = list(catalogues)
        self.objects: list[Object] = []
        self._groups: dict[tuple[int, str], list[Object]] = defaultdict(list)
        self._members: dict[tuple[int, str], list[Object]] = defaultdict(list)
        for rank, catalogue in enumerate(self.catalogues):
            for obj in catalogue.objects:
                obj.catalogue = catalogue.name
                obj.rank = rank
                target = self._groups if obj.is_group else self._members
                for name in obj.groups:
                    for form in indexed_forms(name):
                        target[(rank, full_key(form))].append(obj)
            for obj in catalogue.invalid:  # kept apart, but they know where they belong
                obj.rank = rank
            self.objects.extend(catalogue.objects)
        self.names = NameIndex(self.objects, on_progress)
        # built lazily, on first use of any key of that kind, and cached for the rest of this Collection's
        # life - a Reload makes a new Collection, so none of these can ever go stale; see objects_by_type,
        # objects_by_constellation, objects_by_name and cached_object_ids
        self._by_type: dict[ObjectType, tuple[Object, ...]] | None = None
        self._by_constellation: dict[str, tuple[Object, ...]] | None = None
        self._by_name: dict[str, tuple[Object, ...]] | None = None
        self._id_cache: dict[str, frozenset[int]] = {}

    def groups_named(self, rank: int, name: str) -> list[Object]:
        """The group Objects of one catalogue that have this group name.

        :param rank: the catalogue's rank
        :param name: the group name to look up
        :returns: the matching group Objects
        """
        return self._groups.get((rank, full_key(name)), [])

    def members_named(self, rank: int, name: str) -> list[Object]:
        """The Objects of one catalogue, not groups, that name this group in GROUP.

        :param rank: the catalogue's rank
        :param name: the group name to look up
        :returns: the matching member Objects
        """
        return self._members.get((rank, full_key(name)), [])

    def members_of(self, group: Object) -> list[Object]:
        """The Objects of `group`'s own catalogue that its GROUP name(s) collect - empty for anything
        that is not itself a group (see Object.is_group). A group can carry more than one GROUP name
        (rare); a member named by more than one of them is still counted once.

        :param group: the group to find the members of
        :returns: the group's members
        """
        if not group.is_group:
            return []
        found = {id(m): m for name in group.groups for m in self.members_named(group.rank, name)}
        return list(found.values())

    def group_names(self, rank: int) -> frozenset[str]:
        """Lower-cased names of the group records of one catalogue.

        :param rank: the catalogue's rank
        :returns: the catalogue's group names, lower-cased
        """
        return self.catalogues[rank].group_names

    def objects_by_type(self, object_type: ObjectType) -> tuple[Object, ...]:
        """Every Object (of any catalogue) having `object_type` among its types, in collection order. Built
        once, on first call for any ObjectType, and cached from then on - a filter narrowing by `type` can
        use this to find its candidates directly instead of visiting every Object of the collection to ask.

        :param object_type: the type to look up
        :returns: the Objects having that type
        """
        if self._by_type is None:
            by_type: dict[ObjectType, list[Object]] = defaultdict(list)
            for obj in self.objects:
                for t in obj.types:
                    by_type[t].append(obj)
            self._by_type = {t: tuple(objects) for t, objects in by_type.items()}
        return self._by_type.get(object_type, ())

    def objects_by_constellation(self, constellation: str) -> tuple[Object, ...]:
        """Every Object (of any catalogue) with this constellation, in collection order. `constellation` is
        matched case-insensitively, already lower-cased by the caller (see names.full_key for the same
        convention elsewhere). Built once, on first call for any constellation, and cached from then on.

        :param constellation: the constellation to look up, already case-folded
        :returns: the Objects with that constellation
        """
        if self._by_constellation is None:
            by_constellation: dict[str, list[Object]] = defaultdict(list)
            for obj in self.objects:
                if obj.constellation:
                    by_constellation[obj.constellation.casefold()].append(obj)
            self._by_constellation = {c: tuple(objects) for c, objects in by_constellation.items()}
        return self._by_constellation.get(constellation, ())

    def objects_by_name(self, name: str) -> tuple[Object, ...]:
        """Every Object (of any catalogue) with this name, in collection order. `name` is matched exactly,
        case-insensitively, against an Object's own `names` only - not its `groups`, not the repeated-
        whitespace-collapsing `names.full_key` uses, and not the abbreviation-aware short-form matching
        `NameIndex` adds on top for cross-catalogue references (a filter's `name` criterion means "written
        this way", not "refers to the same star"). Built once, on first call for any name, and cached from
        then on.

        :param name: the name to look up, already case-folded
        :returns: the Objects with that name
        """
        if self._by_name is None:
            by_name: dict[str, list[Object]] = defaultdict(list)
            for obj in self.objects:
                for n in obj.names:
                    by_name[n.casefold()].append(obj)
            self._by_name = {n: tuple(objects) for n, objects in by_name.items()}
        return self._by_name.get(name, ())

    def cached_object_ids(self, key: str, build: Callable[[], frozenset[int]]) -> frozenset[int]:
        """A cache of id-set results, keyed by an arbitrary string meaningful to the caller. Calls `build()`
        once per distinct `key` and reuses that result for the rest of this Collection's life after that -
        used by filters.py to avoid rebuilding a whole project list (see domain.lists.build_list) on every
        single filter evaluation that needs it, without Collection itself needing to know what a "list" is.

        :param key: identifies which cached result to return (e.g. a list's name in domain.lists.LISTS)
        :param build: computes the result when it is not cached yet; not called again once it is
        :returns: the cached, or newly built and now cached, result
        """
        if key not in self._id_cache:
            self._id_cache[key] = build()
        return self._id_cache[key]
