"""Names as the catalogues write them, and how they are matched.

Two Objects can only be the same thing when they share a name, but catalogues write names differently:
in other case and spacing, with the first space left out ("M 31", "M31"), with a short form
("Messier 13", "M13"). Objects also come in kinds that never match one another: a group, a pair
(a double star) and everything else.
"""
import re
from collections import defaultdict
from collections.abc import Callable
from functools import cache

from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType

DEFAULT_COMPONENT = "ab"
GROUP, PAIR, OTHER = "group", "pair", "other"

# a WDS id, e.g. "WDS19307+2758" - always the last name of a double star Group or pair matched to the WDS
WDS_ID = re.compile(r"WDS\d{5}[+-]\d{4}")


# Catalogues of clusters and nebulae have short forms: "Messier 13" is also "M13" - set once per data
# directory load (see set_object_name_abbreviations) from its object_name_abbreviations.json, empty until
# then. The first matching entry applies; {} stands for the rest of the name. Both the long and the short
# form are names.
_Abbreviation = tuple["re.Pattern[str]", list[str]]

_OBJECT_NAME_ABBREVIATION_PATTERNS: list[_Abbreviation] = []
_PATTERNS_BY_FIRST_WORD: dict[str, list[_Abbreviation]] | None = None
_LITERAL_HEAD = re.compile(r"([^\s()\\.*+?\[\]{}|^$]+) \(")  # a pattern that starts with a plain word and a space


def set_object_name_abbreviations(abbreviations: list[tuple[str, list[str]]]) -> None:
    """Replaces the abbreviation patterns name_forms/indexed_forms match against, and clears their cache -
    called once whenever a data directory's object_name_abbreviations.json is (re)read (see
    datadir.discover), so a Reload with an edited file never keeps serving names cached under the previous
    one.

    :param abbreviations: (regex pattern, short-form templates) pairs, in priority order - the first
        matching entry applies; see datadir.read_object_name_abbreviations
    """
    global _OBJECT_NAME_ABBREVIATION_PATTERNS, _PATTERNS_BY_FIRST_WORD  # pylint: disable=global-statement
    _OBJECT_NAME_ABBREVIATION_PATTERNS = [(re.compile(pattern), templates) for pattern, templates in abbreviations]
    _PATTERNS_BY_FIRST_WORD = _by_first_word()
    name_forms.cache_clear()
    indexed_forms.cache_clear()


def _by_first_word() -> dict[str, list[_Abbreviation]] | None:
    """The patterns by the word they start with, in their order, so that a name only meets the ones that can match
    it: 359,000 names (of which 473 have a short form) were tried against every one of them.

    :returns: the patterns by first word, or None when a pattern is not of the form `Word (...)` - then
        every name is tried against every pattern, as before
    """
    table: dict[str, list[_Abbreviation]] = {}
    for entry in _OBJECT_NAME_ABBREVIATION_PATTERNS:
        pattern, _templates = entry
        head = _LITERAL_HEAD.match(pattern.pattern)
        if head is None:
            return None
        table.setdefault(head.group(1), []).append(entry)
    return table


@cache
def name_forms(name: str) -> tuple[str, ...]:
    """The name and its short forms. Cached (pure function of `name`): the same names recur across many
    Objects within one catalogue and, since the static catalogues are kept in memory across reloads,
    across reloads too - building the name index of ~250k objects was otherwise dominated by re-running
    this same regex matching over and over for names already seen.

    :param name: the name to find the forms of
    :returns: the name and its short forms
    """
    candidates = (_OBJECT_NAME_ABBREVIATION_PATTERNS if _PATTERNS_BY_FIRST_WORD is None
                  else _PATTERNS_BY_FIRST_WORD.get(name.partition(" ")[0], ()))
    for pattern, templates in candidates:
        match = pattern.match(name)
        if match:
            return (name, *(template.format(match.group(1)) for template in templates))
    return (name,)


@cache
def indexed_forms(name: str) -> tuple[str, ...]:
    """Every form of a name that finds its Object: the name and its short forms (see name_forms) and, for a name
    that joins several ("NGC6992 & NGC6995 & IC1340"), each of the joined names too. Only the name that is
    looked up is not taken apart, so a joined name is found by its parts and not the other way round.

    :param name: the name to find the indexed forms of
    :returns: its indexed forms
    """
    forms: list[str] = []
    for form in name_forms(name):
        forms.append(form)
        if " & " in form:
            forms.extend(part.strip() for part in form.split("&"))
    return tuple(forms)


def expand_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """The names extended with their short forms (see name_forms) right after each one, for an Object's
    names and groups. This is in-memory only: it is never written back, since the writer renders the
    record a Catalogue was loaded from, not this expanded list.

    :param names: the names to expand
    :returns: the names, each followed by its short forms, duplicates removed
    """
    expanded: list[str] = []
    seen: set[str] = set()
    for name in names:
        for form in name_forms(name):
            if form not in seen:
                seen.add(form)
                expanded.append(form)
    return tuple(expanded)


@cache
def full_key(name: str) -> str:
    """Case-insensitive, repeated whitespace collapsed. Cached, for the same reason as name_forms: the
    same forms recur heavily while building the name index.

    :param name: the name to build a key for
    :returns: the key
    """
    return " ".join(name.split()).casefold()


def compact_key(key: str) -> str:
    """The key without its first space; "M 31" is then found as "M31" and the other way round.

    :param key: a key as built by full_key
    :returns: the key without its first space
    """
    return key.replace(" ", "", 1)


def kind_of(obj: Object) -> str:
    """Whether an Object is a GROUP, a PAIR (a double star, never a group) or OTHER: Objects only ever
    match another of the same kind.

    :param obj: the object to classify
    :returns: GROUP, PAIR or OTHER
    """
    if obj.is_group:
        return GROUP
    return PAIR if ObjectType.DOUBLE_STAR in obj.types else OTHER


STAR_TYPES = frozenset({ObjectType.STAR, ObjectType.VARIABLE_STAR, ObjectType.CARBON_STAR})


def is_star(obj: Object) -> bool:
    """Whether an Object is a star (*, V* or C*), never a double star (**) even though that is also
    "a star" in the everyday sense - the two are told apart everywhere a list or the own catalogue's
    write-back order sorts a star after everything else but still before a double star.

    :param obj: the object to check
    :returns: whether it is a star
    """
    return bool(STAR_TYPES.intersection(obj.types))


def names_of(obj: Object, kind: str) -> tuple[str, ...]:
    """The names an Object of this kind is looked up and matched by: a group's groups, otherwise its names.

    :param obj: the object to find the names of
    :param kind: the object's kind, as kind_of gives it
    :returns: the names to match by
    """
    return obj.groups if kind == GROUP else obj.names


def component_of(obj: Object) -> str:
    """The component of a pair; a pair without one is the pair AB.

    :param obj: the pair to find the component of
    :returns: the component, lower-cased, DEFAULT_COMPONENT when none is given
    """
    return _given_component(obj) or DEFAULT_COMPONENT


def component_name(obj: Object) -> str:
    """The component of a pair as its record writes it (AB, Aa-Ab), without any default: empty when it has none.

    :param obj: the pair to find the component of
    :returns: the component as written, or "" when none is given
    """
    return str(obj.record.get(ObjectAttribute.COMPONENT, "")).split(",", maxsplit=1)[0].strip()


def has_component(obj: Object) -> bool:
    """Whether the pair's record gives a component, so that component_of is not just the default.

    :param obj: the pair to check
    :returns: whether it has a component
    """
    return bool(_given_component(obj))


def _given_component(obj: Object) -> str:
    return str(obj.record.get(ObjectAttribute.COMPONENT, "")).split(",", maxsplit=1)[0].strip().casefold()


def found_only_as_part(group: Object, name: str) -> bool:
    """Whether `name` finds the group only as one of the parts of a joined name ("KU83" for the group
    "KU83 & ARN35"), and is not one of the group's own names.

    :param group: the group `name` found
    :param name: the name it was found by
    :returns: whether it was found only as part of a joined name
    """
    wanted = _lookup_keys(name)
    return not any(wanted & _lookup_keys(own) for own in group.groups)


def _lookup_keys(name: str) -> set[str]:
    """Every key `name` can be looked up by: full_key and compact_key of each of its name_forms.

    :param name: the name to build lookup keys for
    :returns: its lookup keys
    """
    keys: set[str] = set()
    for form in name_forms(name):
        key = full_key(form)
        keys.update((key, compact_key(key)))
    return keys


def same_component(first: str, second: str) -> bool:
    """Whether two component texts name the same stars: the letters of a part are unordered (AB is BA) and so
    are the two parts of a pair of parts (AB-C is C-AB), but the structure is kept (AB-C is not A-BC, and a hyphen
    is not a comma). Used to match the components of community observations; References compare them as written.

    :param first: a component text
    :param second: another component text
    :returns: whether they name the same stars
    """
    return _component_key(first) == _component_key(second)


def component_letters(component: str) -> frozenset[str]:
    """The letters of a component text, whatever separates them: AB,C and AB-C are both a, b and c.

    :param component: the component text
    :returns: its letters, lower-cased
    """
    return frozenset(c for c in component.casefold() if c.isalpha())


def component_key(component: str) -> tuple[str, frozenset[str]]:
    """What two component texts share when they name the same stars (see same_component); it can be a
    dictionary key.

    :param component: the component text
    :returns: its key
    """
    return _component_key(component)


def _component_key(component: str) -> tuple[str, frozenset[str]]:
    """The (separator, sorted-letter-groups) that `component_key` and `same_component` compare by.

    :param component: the component text
    :returns: its key
    """
    text = "".join(component.casefold().split())
    for separator in ("-", ","):
        if separator in text:
            return separator, frozenset("".join(sorted(part)) for part in text.split(separator))
    return "", frozenset(["".join(sorted(text))])


class NameIndex:
    """Looks Objects up by kind and name, in every indexed form of that name."""

    def __init__(self, objects: list[Object], on_progress: Callable[[int, int], None] | None = None):
        """Building this is the dominant cost of loading a large data directory (measured: ~1s of ~1.1s
        for a Collection of 171k real WDS objects), so on_progress, given (objects indexed so far, the
        total), is reported roughly every 1% - fine enough to be useful, coarse enough not to add
        meaningful overhead of its own.

        :param objects: the objects to index
        :param on_progress: reports indexing progress, roughly every 1%
        """
        self._full: dict[tuple[str, str], list[Object]] = defaultdict(list)
        self._compact: dict[tuple[str, str], list[Object]] = defaultdict(list)
        total = len(objects)
        report = on_progress or (lambda done, _total: None)
        step = max(total // 100, 1)
        for index, obj in enumerate(objects):
            kind = kind_of(obj)
            for name in names_of(obj, kind):
                for form in indexed_forms(name):
                    key = full_key(form)
                    self._full[(kind, key)].append(obj)
                    self._compact[(kind, compact_key(key))].append(obj)
            if index % step == 0:
                report(index, total)
        report(total, total)

    def lookup(self, kind: str, name: str) -> list[Object]:
        """Objects with an equal name, or with a name that only differs by the first space.

        :param kind: the kind of object to look up (GROUP, PAIR or OTHER)
        :param name: the name to look up
        :returns: the matching objects
        """
        found: list[Object] = []
        for form in name_forms(name):
            key = full_key(form)
            found += (self._full.get((kind, key), []) + self._full.get((kind, compact_key(key)), [])
                      + self._compact.get((kind, key), []))
        return found
