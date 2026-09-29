"""Reads the Alternative-names file (wds_alternative_names.json): extra names for a double star Group, or
a pair with no Group, beyond what the WDS itself provides (see CONTEXT.md, Alternative name). Nothing
is written back - it is merged onto the matching WDS Object's names each time the data directory loads.

Each entry is one JSON object: `names` (required) is a comma-separated list of names identifying the
Group or pair - any one of them matching is enough, the same as an Object's own several names each find
it; one that matches nothing is a warning, not an error, as long as another one in the same entry still
resolves it (every one matching nothing, or two matching different Objects, is the error case instead).
`alternative_names` (required) is a comma-separated list of names to add. `replace` (optional, default
false) drops every one of the match's own names but its WDS id and puts `alternative_names` there
instead, rather than adding them alongside.

Matching here is a plain exact lookup, built once from the WDS catalogue's own names - narrower than
attach.py's full matcher (no Component, no joined-name or short-form handling), since an entry only
ever names a Group or an ungrouped pair. Deliberately not the shared matcher: that would mean building a
second name index of the whole WDS catalogue on every reload, doubling reload's dominant cost for what
is, in practice, a few hundred exact designations.
"""
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import ERROR, WARNING, Finding
from faint_fuzzies.domain.model import Object, ObjectAttribute, split_names
from faint_fuzzies.domain.names import WDS_ID, full_key
from faint_fuzzies.storage import load_json_list

_SOURCE = "wds_alternative_names.json"


@dataclass(frozen=True)
class AlternativeNames:
    """One entry of the Alternative-names file.

    :ivar names: the comma-separated names identifying the Group or pair to give alternative names to
    :ivar alternative_names: the comma-separated alternative names to give it
    :ivar replace: whether these replace every one of the match's own names but its WDS id, rather than
        adding alongside them
    :ivar line: the entry's 1-based position in the file, for a finding
    """
    names: str
    alternative_names: str
    replace: bool
    line: int


def read_wds_alternative_names(path: Path) -> tuple[list[AlternativeNames], list[Finding]]:
    """Reads the Alternative-names file.

    :param path: the file to read
    :returns: the understood entries, in file order, and a Finding for each entry that was not a JSON
        object with usable `names` and `alternative_names` strings (left out of the entries)
    """
    data = load_json_list(path, "entries")
    entries: list[AlternativeNames] = []
    findings: list[Finding] = []
    for number, raw in enumerate(data, start=1):
        entry = _parse_entry(raw, number)
        if isinstance(entry, str):
            findings.append(Finding(_SOURCE, number, None, "names", ERROR, entry))
        else:
            entries.append(entry)
    return entries, findings


def _parse_entry(raw: Any, number: int) -> AlternativeNames | str:
    if not isinstance(raw, dict):
        return "entry is not a JSON object"
    names = raw.get("names", "")
    alternative_names = raw.get("alternative_names", "")
    if not isinstance(names, str) or not names.strip():
        return "entry has no usable 'names'"
    if not isinstance(alternative_names, str) or not alternative_names.strip():
        return "entry has no usable 'alternative_names'"
    replace = bool(raw.get("replace", False))
    return AlternativeNames(names, alternative_names, replace, number)


def build_name_index(wds_objects: Sequence[Object]) -> dict[str, list[Object]]:
    """The exact-lookup index an Alternative-names entry's own `names` is matched against: every
    Group's own names, and every ungrouped pair's own names, keyed by full_key. A pair that belongs to
    a Group is deliberately left out (see the module docstring) - it shares its Group's own alternative
    name and WDS id, which would otherwise look ambiguous here.

    :param wds_objects: the WDS catalogue's objects to index
    :returns: the index, shared by apply_alternative_names and anything else that needs the identical
        lookup (e.g. a WDS-update safety check, see domain.wds_update_check)
    """
    by_key: dict[str, list[Object]] = defaultdict(list)
    for obj in wds_objects:
        if not obj.is_group and obj.groups:
            continue
        for name in (obj.groups if obj.is_group else obj.names):
            by_key[full_key(name)].append(obj)
    return by_key


def find_by_name(by_key: dict[str, list[Object]], names: Sequence[str]) -> Object | str:
    """The one distinct Object any of `names` finds in `by_key` (see build_name_index) - any one
    matching is enough, the same as an Object's own several names each find it.

    :param by_key: the index to search, from build_name_index
    :param names: the names to try, in order
    :returns: the matched Object, or an error message when none of them matched anything, or two
        matched different Objects
    """
    found = {id(o): o for n in names for o in by_key.get(full_key(n), ())}
    if len(found) == 1:
        return next(iter(found.values()))
    what = "no double star" if not found else f"{len(found)} different double stars"
    joined = ", ".join(f"'{n}'" for n in names)
    return f"{what} named {joined}"


def apply_alternative_names(wds_objects: Sequence[Object], entries: Sequence[AlternativeNames],
                            findings: list[Finding]) -> int:
    """Merges every Alternative-names entry onto its matching double star Group, or pair with no Group.
    An entry that matches nothing, or more than one distinct Object, is reported and left out. Matching a
    Group also adds its new names to every one of its own pairs - a name common to the whole system
    should read that way wherever one of its pairs is shown on its own, not only on the Group itself (see
    CONTEXT.md, Alternative name).

    :param wds_objects: the WDS catalogue's objects, already reset to their pristine names (see
        loading.load_data_dir) - this must run before anything builds a Collection from them, so the
        name index picks up the merge
    :param entries: the Alternative-names file's entries
    :param findings: the list a problem is appended to
    :returns: how many entries were applied
    """
    by_key = build_name_index(wds_objects)
    members_by_group_key: dict[str, list[Object]] = defaultdict(list)
    pristine_groups: dict[int, tuple[str, ...]] = {}
    for obj in wds_objects:
        if not obj.is_group and obj.groups:
            # indexed by its Group's name(s), to add the Group's own new names to it below
            for name in obj.groups:
                members_by_group_key[full_key(name)].append(obj)
            continue
        if obj.is_group:
            pristine_groups[id(obj)] = obj.groups  # before any entry below may replace some of them

    applied = 0
    for entry in entries:
        names = split_names(entry.names)
        target = find_by_name(by_key, names)
        if isinstance(target, str):
            findings.append(Finding(_SOURCE, entry.line, entry.names, "names", ERROR, target))
            continue
        for name in names:
            if not by_key.get(full_key(name)):
                findings.append(Finding(_SOURCE, entry.line, entry.names, "names", WARNING,
                                        f"'{name}' does not match any double star - check it is not a typo"))
        extra = split_names(entry.alternative_names)
        _merge_target_and_members(target, extra, entry.replace, pristine_groups, members_by_group_key)
        applied += 1
    return applied


def _merge_target_and_members(target: Object, extra: Sequence[str], replace: bool,
                              pristine_groups: dict[int, tuple[str, ...]],
                              members_by_group_key: dict[str, list[Object]]) -> None:
    """Merges `extra` onto `target`, and, when it is a Group, onto every one of its own pairs too - a
    name common to the whole system should read that way wherever one of its pairs is shown on its own.
    A replace also drops the name it replaced from every pair that inherited it identically at
    WDS-conversion time (see converters/wds.py), or a pair would keep showing the very name the Group's
    own entry replaced; a pair's own designation is never touched either way. The dropped name comes from
    the Group's *pristine* names, not however they stand right now - an earlier, unrelated entry's own
    addition must survive a later replace of a different name, not be swept up as collateral damage."""
    _merge_names(target, extra, replace)
    if not target.is_group:
        return
    dropped = [n for n in pristine_groups[id(target)] if replace and not WDS_ID.fullmatch(n)]
    members = {id(m): m for name in target.groups for m in members_by_group_key.get(full_key(name), ())}
    for member in members.values():
        _merge_names(member, extra, False, dropped)


def _merge_names(target: Object, extra: Sequence[str], replace: bool, drop: Sequence[str] = ()) -> None:
    """Adds `extra` to `target`'s names (its `groups` when it is a Group, its `names` otherwise), or,
    with `replace`, drops every one of its own names but its WDS id and puts `extra` there instead.
    Without `replace`, `drop` is also removed, if present (used to carry a Group's own replace down to
    one of its pairs, without dropping the pair's own designation along with it). Either way, the WDS id
    (always the last name of a double star matched to the WDS, see domain.names) stays last. Also
    updates `target.record`'s own NAME/GROUP value to match, since display code reads that directly (see
    site/objects.py's get_display_names) rather than the parsed names/groups."""
    attribute = "groups" if target.is_group else "names"
    current = list(getattr(target, attribute))
    wds_id = next((n for n in current if WDS_ID.fullmatch(n)), None)
    if replace:
        new_names = [*extra, *([wds_id] if wds_id else [])]
    else:
        existing_keys = {full_key(n) for n in current}
        drop_keys = {full_key(n) for n in drop}
        without = [n for n in current if n != wds_id and full_key(n) not in drop_keys]
        if not without and drop_keys:
            # every one of this Object's own names was in `drop` (a pair whose only name(s) happen to
            # be exactly the Group's own, shared verbatim by every one of its pairs, see converters/wds.py)
            # - dropping them would leave it with nothing to be found by at all, worse than still
            # showing a name a Group-level replace dropped, so it keeps them
            without = [n for n in current if n != wds_id]
        new_names = without + [n for n in extra if full_key(n) not in existing_keys] \
            + ([wds_id] if wds_id else [])
    setattr(target, attribute, tuple(new_names))
    record_key = ObjectAttribute.GROUP if target.is_group else ObjectAttribute.NAME
    target.record[record_key] = ", ".join(new_names)
