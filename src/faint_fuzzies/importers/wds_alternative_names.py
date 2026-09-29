"""Reads the Alternative-names file (wds_alternative_names.json): extra names for a double star Group, a
pair with no Group, or one specific pair of a Group, beyond what the WDS itself provides (see
CONTEXT.md, Alternative name). Nothing is written back - it is merged onto the matching WDS Object's
names each time the data directory loads.

Each entry is one JSON object: `name` (required) is a comma-separated list of names identifying the
Group or pair - any one of them matching is enough, the same as an Object's own several names each find
it; one that matches nothing is a warning, not an error, as long as another one in the same entry still
resolves it (every one matching nothing, or two matching different Objects, is the error case instead).
`alternative_name` (required) is a comma-separated list of names to add. `replace` (optional, default
false) drops every one of the match's own names but its WDS id and puts `alternative_name` there
instead, rather than adding them alongside. `component` (optional) narrows a match that resolves to a
Group down to the one of its pairs with that Component (AB and BA are the same Component) - the
Group itself and its other pairs are left untouched; giving a `component` when `name` resolves to an
already-ungrouped pair, or to no pair of the Group with that Component, is an error. Two or more
entries that end up addressing the exact same Group or pair are each given a warning naming the
others - normal when deliberately splitting several alternative names across entries, but just as
easily an accidental duplicate.

Matching here is a plain exact lookup, built once from the WDS catalogue's own names - narrower than
attach.py's full matcher (no joined-name or short-form handling), since an entry only ever names a
Group or an ungrouped pair before any `component` narrows it further. Deliberately not the shared
matcher: that would mean building a second name index of the whole WDS catalogue on every reload,
doubling reload's dominant cost for what is, in practice, a few hundred exact designations.
"""
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.findings import ERROR, WARNING, Finding
from faint_fuzzies.domain.model import Object, ObjectAttribute, split_names
from faint_fuzzies.domain.names import WDS_ID, component_of, full_key, same_component
from faint_fuzzies.storage import load_json_list

_SOURCE = "wds_alternative_names.json"


@dataclass(frozen=True)
class AlternativeNames:
    """One entry of the Alternative-names file.

    :ivar name: the comma-separated names identifying the Group or pair to give alternative names to
    :ivar alternative_name: the comma-separated alternative names to give it
    :ivar component: the Component of the Group's one pair to target instead of the Group itself; empty
        when the entry targets `name`'s own match directly
    :ivar replace: whether these replace every one of the match's own names but its WDS id, rather than
        adding alongside them
    :ivar line: the entry's 1-based position in the file, for a finding
    """
    name: str
    alternative_name: str
    component: str
    replace: bool
    line: int


def read_wds_alternative_names(path: Path) -> tuple[list[AlternativeNames], list[Finding]]:
    """Reads the Alternative-names file.

    :param path: the file to read
    :returns: the understood entries, in file order, and a Finding for each entry that was not a JSON
        object with usable `name` and `alternative_name` strings (left out of the entries)
    """
    data = load_json_list(path, "entries")
    entries: list[AlternativeNames] = []
    findings: list[Finding] = []
    for number, raw in enumerate(data, start=1):
        entry = _parse_entry(raw, number)
        if isinstance(entry, str):
            findings.append(Finding(_SOURCE, number, None, "name", ERROR, entry))
        else:
            entries.append(entry)
    return entries, findings


def _parse_entry(raw: Any, number: int) -> AlternativeNames | str:
    if not isinstance(raw, dict):
        return "entry is not a JSON object"
    name = raw.get("name", "")
    alternative_name = raw.get("alternative_name", "")
    if not isinstance(name, str) or not name.strip():
        return "entry has no usable 'name'"
    if not isinstance(alternative_name, str) or not alternative_name.strip():
        return "entry has no usable 'alternative_name'"
    component = str(raw.get("component", "") or "").strip()
    replace = bool(raw.get("replace", False))
    return AlternativeNames(name, alternative_name, component, replace, number)


def build_name_index(wds_objects: Sequence[Object]) -> dict[str, list[Object]]:
    """The exact-lookup index an Alternative-names entry's own `name` is matched against: every
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
    """Merges every Alternative-names entry onto its matching double star Group, pair with no Group, or
    (when `component` is given) one specific pair of a matched Group. An entry that matches nothing, or
    more than one distinct Object, is reported and left out, the same as one whose `component` does not
    apply (the match is not a Group) or names no pair of the Group (or more than one). Matching a Group
    directly also adds its new names to every one of its own pairs - a name common to the whole system
    should read that way wherever one of its pairs is shown on its own, not only on the Group itself; a
    Group matched only to narrow it to one pair via `component` does not (see CONTEXT.md, Alternative
    name). Two or more entries that end up addressing the exact same Group or pair are each given a
    warning naming the others, since that is normal when deliberately splitting several alternative
    names across entries, but just as easily an accidental duplicate.

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
    addressed_lines: dict[int, list[int]] = defaultdict(list)
    addressed_target: dict[int, Object] = {}
    for entry in entries:
        names = split_names(entry.name)
        target = find_by_name(by_key, names)
        if isinstance(target, str):
            findings.append(Finding(_SOURCE, entry.line, entry.name, "name", ERROR, target))
            continue
        if entry.component:
            narrowed = _pair_with_component(target, entry.component, members_by_group_key)
            if isinstance(narrowed, str):
                findings.append(Finding(_SOURCE, entry.line, entry.name, "component", ERROR, narrowed))
                continue
            target = narrowed
        # checked against the target actually resolved to (its own pair, once `component` has narrowed
        # it there), not `by_key` alone - that index deliberately leaves out a grouped pair's own names
        # (see build_name_index), which `name` may legitimately be one of once `component` narrows to it
        target_names = {full_key(n) for n in (target.groups if target.is_group else target.names)}
        for name in names:
            if full_key(name) not in target_names:
                findings.append(Finding(_SOURCE, entry.line, entry.name, "name", WARNING,
                                        f"'{name}' does not match any double star - check it is not a typo"))
        addressed_lines[id(target)].append(entry.line)
        addressed_target[id(target)] = target
        extra = split_names(entry.alternative_name)
        _merge_target_and_members(target, extra, entry.replace, pristine_groups, members_by_group_key)
        applied += 1
    for key, lines in addressed_lines.items():
        if len(lines) <= 1:
            continue
        target = addressed_target[key]
        kind = "Group" if target.is_group else "pair"
        for line in lines:
            others = ", ".join(str(n) for n in lines if n != line)
            findings.append(Finding(_SOURCE, line, target.label, "name", WARNING,
                                    f"addresses the same {kind} ({target.label}) as line {others} - "
                                    f"make sure that is intentional, not an accidental duplicate"))
    return applied


def _pair_with_component(target: Object, component: str,
                         members_by_group_key: dict[str, list[Object]]) -> Object | str:
    """The one pair of Group `target` with `component` (AB and BA are the same Component), to narrow an
    Alternative-names entry to it instead of the whole Group.

    :param target: the Object an entry's own `name` matched
    :param component: the Component to narrow it to
    :param members_by_group_key: every Group's own pairs, by its name's full_key (see
        apply_alternative_names)
    :returns: the one pair with that Component, or an error message when `target` is not a Group, or it
        has no pair with that Component, or more than one
    """
    if not target.is_group:
        return f"'{target.label}' is not a Group; 'component' does not apply"
    members = {id(m): m for name in target.groups for m in members_by_group_key.get(full_key(name), ())}
    matches = [m for m in members.values() if same_component(component_of(m), component)]
    if len(matches) == 1:
        return matches[0]
    what = "no pair" if not matches else f"{len(matches)} pairs"
    return f"'{target.label}' has {what} with component {component}"


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
