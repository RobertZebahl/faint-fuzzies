"""Attaches the observations of community files to Objects, while loading. Nothing is written back.

Each observation goes to one Object. The catalogues are searched in the order they are given, so the
own catalogue goes first and the WDS after it:

* A double star row names a double star and a component. A name and a component identify a pair,
  which may be named directly or be a member of the group of that name (AB and BA are the same component,
  see names.same_component); a name alone identifies the group when there is one, otherwise the single pair
  or the one system that several pairs form. A group that the name finds only as one part of a joined name
  ("KU83" in "KU83 & ARN35") comes after the pair AB of that exact name, and before any other pair.
* A component of "*" means more than one component was observed: the row goes to the group of the name
  (the group it names directly, the one system several pairs of the name form, or - when the name is one
  pair - the group that pair belongs to); a single pair that belongs to no group is attached anyway, with
  a warning, since there is nothing bigger to attach it to.
* Without a component, a name that is a group, or that names several pairs of one system, is attached to
  the group anyway, with a warning suggesting "*" instead; a name of one pair goes to it directly, with an
  info when its component is not the trivial AB.
* A component that matches no pair of the name exactly is attached anyway, with a warning, as long as the
  name is not itself ambiguous: to the group when the name is a group's or several pairs' of one system,
  otherwise to the one pair of the name (the warning names another pair of its system that has the
  component, if there is one: was the name or the component wrong?). Only a name of several pairs that
  form no one system, or of several groups, stays a problem.
* A deep sky row names an object or a group of the first catalogue only, and its object type tells
  apart objects that share a name.
* A row's name may be a comma-separated list of several names for the same star or object (see
  match_any_name) - any one matching is enough, with a warning for each other name that matches
  nothing, as long as they do not resolve to different Objects.

A row that matches nothing, or several Objects, is reported and left out.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.findings import ERROR, INFO, WARNING, CatalogueError, Finding
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType, split_names
from faint_fuzzies.domain.names import (
    DEFAULT_COMPONENT,
    GROUP,
    OTHER,
    PAIR,
    component_of,
    found_only_as_part,
    has_component,
    kind_of,
    same_component,
)
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.importers.common import Candidate, read_rows, source_name
from faint_fuzzies.importers.global_parser import parse_global
from faint_fuzzies.importers.owner_double_stars import OwnerDoubleStar
from faint_fuzzies.importers.project_deep_sky_with_binoculars_parser import parse_deep_sky_binoculars
from faint_fuzzies.importers.project_double_stars_parser import parse_double_stars

_NO_OBSERVATION = Observation(record={}, public=True, optic=None, visibility=())  # Candidate needs one; unused here

FORMATS = {
    "project-double-stars-visual": "the Double Stars format, visual observations with sketches",
    "project-double-stars-photographic": "the Double Stars format, photographs",
    "project-deep-sky-with-binoculars": "the Deep Sky With Binoculars format",
    "global": "the Global format",
}


@dataclass(frozen=True)
class CommunitySource:
    """One community file to attach.

    :ivar format: the file's format, a key of :data:`FORMATS`
    :ivar observer_id: the id of the observer the file belongs to
    :ivar path: the file's path
    """
    format: str
    observer_id: str
    path: Path


@dataclass
class CommunityResult:
    """The result of :func:`attach_community`.

    :ivar rows: the number of rows read, across every source
    :ivar attached: the number of rows attached to an Object
    :ivar findings: every finding made, across every source
    :ivar on_objects: the warnings and info about a row that matched an Object, as they are shown on that
        Object (naming the row, the Object it was attached to)
    :ivar targets: the Object a row's finding was attached to, by id() of the finding in `findings`, for a
        link from it to the Object
    """
    rows: int = 0
    attached: int = 0
    findings: list[Finding] = field(default_factory=list)
    on_objects: list[tuple[Object, Finding]] = field(default_factory=list)
    targets: dict[int, Object] = field(default_factory=dict)

    @property
    def failed(self) -> int:
        """The number of distinct (catalogue, row) pairs with at least one error."""
        return len({(p.catalogue, p.record) for p in self.findings if p.severity == ERROR})


def attach_community(collection: Collection, observers: Observers | None,
                    sources: Sequence[CommunitySource]) -> CommunityResult:
    """Parses every source and attaches its rows to `collection`'s Objects; see the module docstring for how
    a row is matched.

    :param collection: the collection to attach rows to
    :param observers: the known observers; a source whose observer_id is not among them is an error
    :param sources: the community files to attach, in the order their rows should be reported in
    :returns: the result of attaching every source
    :raises faint_fuzzies.domain.findings.CatalogueError: when a source's observer_id is not in `observers`
    """
    result = CommunityResult()
    matcher = Matcher(collection)
    for source in sources:
        observer = observers.get(source.observer_id) if observers else None
        if observer is None:
            raise CatalogueError(f"unknown observer '{source.observer_id}' (not in the observers file)")
        rows = read_rows(source.path)
        parse: Callable[[], list[Candidate]] = {
            "project-double-stars-visual": lambda _rows=rows, _source=source, _observer=observer:
                parse_double_stars(_rows, _source.path, _observer, True, result.findings),
            "project-double-stars-photographic": lambda _rows=rows, _source=source, _observer=observer:
                parse_double_stars(_rows, _source.path, _observer, False, result.findings),
            "project-deep-sky-with-binoculars": lambda _rows=rows, _source=source, _observer=observer:
                parse_deep_sky_binoculars(_rows, _source.path, _observer, result.findings),
            "global": lambda _rows=rows, _source=source, _observer=observer:
                parse_global(_rows, _source.path, _observer, result.findings),
        }[source.format]
        result.rows += len(rows)
        first = len(result.findings)
        for candidate in parse():
            before = len(result.findings)
            names = split_names(candidate.name)
            target = (match_any_name(matcher, names, candidate.component, source_name(source.path),
                                     candidate.line, candidate.name, result.findings,
                                     object_type=candidate.object_type, double_star=candidate.double_star)
                     if len(names) > 1 else matcher.find(candidate, source_name(source.path), result.findings))
            if target is not None:
                for p in result.findings[before:]:
                    if p.severity in (WARNING, INFO):
                        result.on_objects.append((target, Finding(target.catalogue, target.number, target.label,
                                                                  p.attribute, p.severity,
                                                                  f"{p.catalogue} line {p.record}: {p.message}")))
                        result.targets[id(p)] = target
                candidate.observation.format = source.format
                target.community_observations.append(candidate.observation)
                result.attached += 1
        result.findings[first:] = sorted(result.findings[first:], key=lambda _p: _p.record)
    return result




def _is_pair(obj: Object) -> bool:
    return kind_of(obj) == PAIR


def _pair_component_text(pair: Object) -> str:
    return f"is {component_of(pair)}" if has_component(pair) else "has no component, so it counts as ab"


def _components_text(components: set[str], without_component: int) -> str:
    """What the message says the name has: the components its pairs give and, apart from those, how many
    pairs give none (they count as AB, which is not a component the catalogue names).

    :param components: the components the name's pairs give, apart from those without one
    :param without_component: how many of the name's pairs give no component
    :returns: the message fragment
    """
    parts = []
    if components:
        parts.append(f"it has {', '.join(sorted(components))}")
    if without_component == 1:
        parts.append("one pair has no component, so it counts as ab" if components
                     else "its pair has no component, so it counts as ab")
    elif without_component:
        parts.append(f"{without_component} pairs have no component, so they count as ab")
    return "; ".join(parts)


def _unique(objects: list[Object]) -> list[Object]:
    return list({id(o): o for o in objects}.values())


class Matcher:
    """Matches the Candidates of one collection's rows to its Objects; see the module docstring for the rule."""

    def __init__(self, collection: Collection):
        self._collection = collection

    def _lookup(self, kind: str, name: str, rank: int) -> list[Object]:
        """The Objects of `kind` ("group", "pair" or "other") named `name` in the catalogue of rank `rank`."""
        return _unique([o for o in self._collection.names.lookup(kind, name) if o.rank == rank])

    def _members_of(self, rank: int, groups: list[Object]) -> list[Object]:
        """The members, in the catalogue of rank `rank`, of every group among `groups` (by any of its names)."""
        return _unique([m for g in groups for name in g.groups for m in self._collection.members_named(rank, name)])

    def _member_pairs_text(self, group: Object) -> str:
        """" (name1, name2, ...)" of a group's own pairs, duplicates removed (several pairs of a system
        may share the same designation, see converters.wds) - for appending to a message that names the
        group - its own name is often just the WDS id, so the pairs' own names (a discoverer designation,
        typically) are what makes the message useful; "" when it has none."""
        names = dict.fromkeys(m.label for m in self._collection.members_of(group) if _is_pair(m))
        return f" ({', '.join(names)})" if names else ""

    def find(self, candidate: Candidate, source: str, findings: list[Finding]) -> Object | None:
        """Matches one Candidate to an Object, appending any info, warning or error to `findings`.

        :param candidate: the row to match
        :param source: the name of the file the row is in, as
            :func:`faint_fuzzies.importers.common.source_name` gives it
        :param findings: the list an info, warning or error is appended to
        :returns: the matched Object, or None when the row is left out
        """
        found = (self._match_double_star(candidate) if candidate.double_star
                else self._match_deep_sky(candidate))
        if isinstance(found, tuple):
            found, message, *severity = found
            findings.append(Finding(source, candidate.line, candidate.name, ObjectAttribute.NAME,
                                    severity[0] if severity else WARNING, message))
        if isinstance(found, str):
            findings.append(Finding(source, candidate.line, candidate.name, ObjectAttribute.NAME, ERROR, found))
            return None
        return found

    def _match_double_star(self, candidate: Candidate) -> Object | str | tuple[Object, str] | tuple[Object, str, str]:
        """Matches a double star Candidate; see the module docstring for the rule.

        :param candidate: the row to match
        :returns: the matched Object; an (Object, message) pair when it was attached with a warning, or an
            (Object, message, severity) triple for another severity (currently only INFO); or an error
            message when it matches nothing or several Objects
        """
        name, component = candidate.name, candidate.component.strip()
        if component == "*":
            return self._match_star(name)
        if component:
            return self._match_given_component(name, component)
        return self._match_no_component(name)

    def _match_no_component(self, name: str) -> Object | str | tuple[Object, str] | tuple[Object, str, str]:
        """A row without a component: see the module docstring.

        :param name: the row's name
        :returns: see :meth:`_match_double_star`
        """
        for rank in range(len(self._collection.catalogues)):
            groups = self._lookup(GROUP, name, rank)
            pairs = self._lookup(PAIR, name, rank)
            if not groups and not pairs:
                continue
            # a name that is only a part of a joined group name ("KU83" of "KU83 & ARN35") is a weaker
            # match than the exact name of the one pair AB, but not than that of another pair (SHJ315 ad)
            # or than a name of several pairs, which is the system
            candidates = [g for g in groups if not found_only_as_part(g, name)]
            if not candidates:
                prefer_pair = len(pairs) == 1
                candidates = pairs if groups and prefer_pair else groups or pairs
            if len(candidates) == 1:
                found = candidates[0]
                if kind_of(found) == GROUP:
                    return found, (f"'{name}' is the group {found.label}{self._member_pairs_text(found)}; "
                                   f"give '*' to say so explicitly")
                if has_component(found) and component_of(found) != DEFAULT_COMPONENT:
                    return found, f"'{name}' is the pair {component_of(found)}", INFO
                return found
            system = self._common_group(rank, pairs)
            if system is not None:
                return system, (f"'{name}' matches {len(pairs)} pairs of the group "
                                f"{system.label}{self._member_pairs_text(system)}; give '*' to say so explicitly")
            return f"'{name}' matches {len(candidates)} pairs; give the component"
        return f"no double star named '{name}'"

    def _match_star(self, name: str) -> Object | str | tuple[Object, str]:
        """A row for more than one component ('*'): see the module docstring.

        :param name: the row's name
        :returns: see :meth:`_match_double_star`
        """
        for rank in range(len(self._collection.catalogues)):
            groups = self._lookup(GROUP, name, rank)
            pairs = self._lookup(PAIR, name, rank)
            if not groups and not pairs:
                continue
            candidates = [g for g in groups if not found_only_as_part(g, name)]
            if candidates:
                if len(candidates) == 1:
                    return candidates[0]
                return f"'{name}' matches {len(candidates)} groups; '*' cannot tell them apart"
            if len(pairs) == 1:
                pair = pairs[0]
                system = self._system_of(pair, rank)
                if system is not None:
                    return system
                return pair, f"'*' on '{name}' names one pair with no group of its own; attached to it anyway"
            system = self._common_group(rank, pairs)
            if system is not None:
                return system
            return f"'{name}' matches {len(pairs)} pairs that are not one system; '*' cannot tell them apart"
        return f"no double star named '{name}'"

    def _system_of(self, pair: Object, rank: int) -> Object | None:
        """The one group `pair` belongs to, or None when it belongs to none (or, in principle, more than one).

        :param pair: the pair to find the group of
        :param rank: the catalogue rank the pair belongs to
        :returns: the group, or None
        """
        groups = _unique([g for name in pair.groups for g in self._lookup(GROUP, name, rank)])
        return groups[0] if len(groups) == 1 else None

    def _match_given_component(self, name: str, component: str) -> Object | str | tuple[Object, str]:
        """A row with a specific component text (not '*', not empty): an exact match (AB and BA are the same
        component) wins outright - silently when `name` is either the pair itself names or a true name of
        its group (the group is deliberately what was meant, so resolving to whichever member has the
        component is the point, not a mistake), with a warning when `name` is only a part of a joined
        group name and the match came from a sibling pair found that way (named's own component, if it has
        one, did not match - the match came from searching the whole group, see `_members_of`), since that
        could equally be a typo in the name or in the component. Otherwise see :meth:`_fallback`.

        :param name: the row's name
        :param component: the row's component text, as written
        :returns: see :meth:`_match_double_star`
        """
        seen_components: set[str] = set()
        without_component = 0  # pairs whose record gives no component, so that they only count as AB
        for rank in range(len(self._collection.catalogues)):
            groups = self._lookup(GROUP, name, rank)
            pairs = self._lookup(PAIR, name, rank)
            named_pairs = _unique(pairs + [m for m in self._members_of(rank, groups) if _is_pair(m)])
            seen_components.update(component_of(p) for p in named_pairs if has_component(p))
            without_component += sum(1 for p in named_pairs if not has_component(p))
            matches = [p for p in named_pairs if same_component(component_of(p), component)]
            if len(matches) > 1:
                return f"'{name}' with component {component} matches {len(matches)} pairs"
            if matches:
                match = matches[0]
                if match not in pairs and all(found_only_as_part(g, name) for g in groups):
                    return match, (f"'{name}' has no pair with component {component}, but its group's pair "
                                   f"{match.label} does - was the name or the component wrong?")
                return match
        if seen_components or without_component:
            message = (f"'{name}' has no pair with component {component} "
                       f"({_components_text(seen_components, without_component)})")
            return self._fallback(name, component) or message
        return f"no double star named '{name}'"

    def _fallback(self, name: str, component: str) -> tuple[Object, str] | None:
        """The Object a row with a component no pair has is attached to anyway, and the warning that says
        why; None when the name does not point to one Object (several pairs that form no one system, or
        several groups - either way, '*' cannot resolve it either). Only the first catalogue that knows the
        name is considered.

        :param name: the row's name
        :param component: the row's component text, as written
        :returns: the (Object, warning) pair, or None when no single Object can be chosen
        """
        for rank in range(len(self._collection.catalogues)):
            groups = self._lookup(GROUP, name, rank)
            named_pairs = _unique(self._lookup(PAIR, name, rank)
                                  + [m for m in self._members_of(rank, groups) if _is_pair(m)])
            if not named_pairs:
                continue
            exact_pairs = self._lookup(PAIR, name, rank)
            if len(exact_pairs) == 1 and all(found_only_as_part(g, name) for g in groups):
                # the name of one pair, that is also a part of a joined group name ("STF608" of "HU555 & STF608"):
                # the pair, not the system
                named_pairs, groups = exact_pairs, []
            if groups or len(named_pairs) > 1:
                if groups:
                    system = groups[0] if len(groups) == 1 else None
                else:
                    system = self._common_group(rank, named_pairs)
                if system is None:
                    return None
                return system, (f"'{name}' has no pair with component {component}; attached to the group "
                                f"{system.label}{self._member_pairs_text(system)}, give '*' to say so explicitly")
            pair = named_pairs[0]
            what = f"'{name}' has no component {component} (its pair {_pair_component_text(pair)})"
            groups_of_pair = _unique([g for group_name in pair.groups for g in self._lookup(GROUP, group_name, rank)])
            others = [m for m in self._members_of(rank, groups_of_pair) if _is_pair(m) and m is not pair
                      and same_component(component_of(m), component)]
            if others:
                alternatives = ", ".join(f"{o.label} ({component_of(o)})" for o in others[:3])
                return pair, (f"{what}; attached to it. The pair {alternatives} of the same system has that "
                              f"component: was the name or the component wrong?")
            return pair, f"{what}; attached to it anyway"
        return None

    def _common_group(self, rank: int, pairs: list[Object]) -> Object | None:
        """The one group that all the pairs belong to, when they are the pairs of one system.

        :param rank: the catalogue rank the pairs and the group belong to
        :param pairs: the pairs to find the common group of
        :returns: the common group, or None when there is none or more than one
        """
        groups = [_unique([g for name in pair.groups for g in self._lookup(GROUP, name, rank)]) for pair in pairs]
        first = groups[0] if groups else []
        common = [g for g in first if all(g in others for others in groups)]
        return common[0] if len(common) == 1 else None

    def _match_deep_sky(self, candidate: Candidate) -> Object | str:
        """Matches a deep sky Candidate: an object or a group of the first catalogue only, its object type
        telling apart objects that share a name.

        :param candidate: the row to match
        :returns: the matched Object, or an error message when it matches nothing or several Objects
        """
        name = candidate.name
        objects = _unique(self._lookup(OTHER, name, 0) + self._lookup(GROUP, name, 0))
        if candidate.object_type is not None:
            typed = [o for o in objects if candidate.object_type in o.types]
            if objects and not typed:
                types = ", ".join(sorted({t.value for o in objects for t in o.types})) or "none"
                return f"'{name}' exists, but not as {candidate.object_type.value} (it is {types})"
            objects = typed
        if len(objects) == 1:
            return objects[0]
        if objects:
            return f"'{name}' matches {len(objects)} objects; give the object type"
        return f"no object named '{name}'"


def match_any_name(matcher: Matcher, names: Sequence[str], component: str, source: str, record: int,
                    label: str | None, findings: list[Finding], targets: dict[int, Object] | None = None,
                    object_type: ObjectType | None = None, double_star: bool = True) -> Object | None:
    """Matches a record that may give several names of the same star or object (an Object's own NAME
    list, an Alternative-names entry's key, or a community row's name) by trying each one in turn with
    the same component, the way the matched Object's own several names would each find it. A single
    successful name is enough to attach, with a warning carrying every other name's own reason for not
    resolving it alone (no match, an ambiguous match, or anything else matcher.find reports); an error
    instead when none of the names match at all, or when two different names resolve to two different
    Objects.

    :param matcher: the matcher to try each name with
    :param names: the names to try, in order
    :param component: the component to match with (blank, exact text, or "*"); double stars only
    :param source: the file name, for a finding
    :param record: the record's position in the file, for a finding
    :param label: the record's own label, for a finding
    :param findings: the list a finding is appended to when nothing or several Objects are found
    :param targets: when given, filled in with the matched Object by id() of each info/warning finding
        about a successful match (the same record's own position has no Object of its own to look one up
        by - a double-star attach-record is not among its catalogue's own objects, see
        domain.catalogue_order), for a link from it to the Object it matched
    :param object_type: the object type, for a deep sky record whose type tells same-named objects apart
    :param double_star: whether the record is a double star, rather than a deep sky object
    :returns: the matched Object, or None when nothing (or more than one distinct Object) matched
    """
    kind = "double star" if double_star else "object"
    found: dict[int, Object] = {}
    kept: list[Finding] = []
    not_matched: list[Finding] = []
    for name in names:
        candidate = Candidate(record, name, component, object_type, double_star, _NO_OBSERVATION)
        local: list[Finding] = []
        target = matcher.find(candidate, source, local)
        if target is not None:
            found[id(target)] = target
            kept = local
        else:
            not_matched.extend(Finding(p.catalogue, p.record, p.object, p.attribute, WARNING, p.message)
                               for p in local)
    if len(found) == 1:
        target = next(iter(found.values()))
        findings.extend(kept)
        findings.extend(not_matched)
        if targets is not None:
            for p in (*kept, *not_matched):
                targets[id(p)] = target
        return target
    joined = ", ".join(f"'{n}'" for n in names)
    if found:
        findings.append(Finding(source, record, label, ObjectAttribute.NAME, ERROR,
                                f"{joined} match {len(found)} different {'WDS entries' if double_star else 'objects'}"))
    else:
        findings.append(Finding(source, record, label, ObjectAttribute.NAME, ERROR,
                                f"no {kind} named {joined}"))
    return None


def attach_owner_double_stars(collection: Collection, stars: Sequence[OwnerDoubleStar], source: str,
                              findings: list[Finding], targets: dict[int, Object] | None = None) -> int:
    """Matches the own catalogue's double-star attach-records to their WDS pair or group, the same way
    a Community row is matched (see the module docstring), and merges each one's OBSERVATIONS and tags
    (RATING, PROJECT_DOUBLE_STARS_LISTS, NOTES, DISABLE_PROJECT_DOUBLE_STARS,
    PUBLISH_WITHOUT_OBSERVATION) onto the match. A record that matches nothing, or several Objects, is
    reported and left out, the same as for a Community row.

    Unlike attach_community, this merges directly onto the match's own `observations`/`record` rather
    than `community_observations`: these are the owner's own observations (can be Private, and the
    owner's own Grade/Rating/tag reads already look at `observations`/`record` directly, not through
    community_observations - see domain.seen, ui.statistics, domain.filters).

    :param collection: the collection to attach to (must already include the WDS)
    :param stars: the own catalogue's double-star attach-records (see
        importers.owner_double_stars.read_owner_double_stars)
    :param source: the own catalogue's file name, for findings
    :param findings: the list a record's findings are appended to
    :param targets: when given, filled in with the matched Object by id() of each info/warning finding
        about a successful match (see match_any_name), for a link from it to the Object on the Log page
    :returns: how many records were attached
    """
    matcher = Matcher(collection)
    attached = 0
    for star in stars:
        names = split_names(star.name)
        target = match_any_name(matcher, names, star.component, source, star.number, star.name, findings,
                                targets)
        if target is None:
            continue
        for attribute, value in star.tags.items():
            target.record[attribute] = value
        if star.observations:
            target.observations = target.observations + star.observations
        attached += 1
    return attached
