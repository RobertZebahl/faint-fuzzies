"""The checks that need more than one record, or files next to the catalogue: a name that looks like a Herschel
object without a Herschel reference, the files the own observations refer to, optic codes without a name,
an own-catalogue object outside the Solar System without coordinates or without a constellation, a double
star pair and its Group not naming each other both ways, a double star pair with no reference to the WDS,
two own-catalogue pairs with the same name and Component, an own-catalogue Group whose own pairs exactly
match, completely or in part, the pairs of one WDS group, and an own-catalogue Object whose CONSTELLATION
disagrees with the one computed from its own COORDINATES. `validate` runs
them, and so does loading a data directory (see `load_findings`), which shows them next to the Objects they concern.
Two more checks are opt-in, on request only, never part of loading: `reference_findings` (objects that
reference several objects of one catalogue - real catalogues have many harmless cases, see `--references`) and
`duplicate_name_findings` (see `--duplicate-names`)."""
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from faint_fuzzies.datadir import (
    OWNER_MEDIA_FOLDERS,
    object_name_abbreviations_file,
    optic_names_file,
    owner_media_folder,
    read_object_name_abbreviations,
    read_optic_names,
)
from faint_fuzzies.domain.catalogue import record_numbers
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.findings import ERROR, INFO, WARNING, Finding
from faint_fuzzies.domain.lists import Entry, herschel_names_without_reference
from faint_fuzzies.domain.model import Object, ObjectAttribute, ObjectType, ObservationAttribute, split_names
from faint_fuzzies.domain.names import PAIR, component_key, component_name, component_of, full_key, kind_of
from faint_fuzzies.domain.references import References, wds_reference
from faint_fuzzies.importers.common import missing_files
from faint_fuzzies.site.listpages import PAGE_DESCRIPTIONS_FILE, read_page_descriptions


def load_findings(root: Path, collection: Collection, references: References) -> list[Finding]:
    """The checks of a data directory that loading runs: all of them, but for the own catalogue and what concerns
    it. The other catalogues come from the converters, so their objects are only checked by `validate`.

    :param root: the data directory
    :param collection: the loaded collection
    :param references: the collection's cross-catalogue references
    :returns: the findings found
    """
    own = collection.catalogues[0].objects
    optic_names_path = optic_names_file(root)
    optic_names, optic_names_why = read_optic_names(root) if optic_names_path is not None else ({}, None)
    return [*herschel_findings(collection, references),
            *own_media_findings(root, own),
            *optic_names_file_findings(root),
            *(optic_name_findings(collection.objects, optic_names, optic_names_path.name)
             if optic_names_path is not None and not optic_names_why else []),
            *missing_coordinates_findings(collection, references),
            *missing_constellation_findings(collection),
            *group_existence_findings(collection),
            *orphan_group_findings(collection),
            *wds_reference_findings(collection, references),
            *constellation_findings(collection),
            *duplicate_pair_findings(collection),
            *redundant_group_findings(collection, references)]


def reference_findings(references: References, objects: list[Object] | None = None) -> list[Finding]:
    """A warning for each Object that references several Objects of one catalogue; `objects` limits it to those.
    Opt-in only (see `--references`), never part of `load_findings`: real catalogues have many harmless cases
    of this (a too common name, or an object another catalogue happens to list twice), and the one case that is
    always a real problem - a double star pair's relationship to the WDS not being exactly one-to-one - has its
    own, always-on check (see `wds_reference_findings`).

    :param references: the collection's cross-catalogue references
    :param objects: limits the check to these Objects; every Object when not given
    :returns: the findings found
    """
    findings = []
    for obj, other_catalogue, others in references.ambiguities(objects):
        labels = ", ".join(o.label for o in others[:5]) + (", ..." if len(others) > 5 else "")
        findings.append(Finding(obj.catalogue, obj.number, obj.label,
                                ObjectAttribute.GROUP if obj.is_group else ObjectAttribute.NAME, WARNING,
                                f"references {len(others)} objects in {other_catalogue}: {labels}"))
    return findings


def missing_coordinates_findings(collection: Collection, references: References) -> list[Finding]:
    """An error for each own-catalogue object without coordinates: the website shows them for every object
    that is not part of the Solar System (type S), so building it would stop there - whether or not the
    object is actually published yet, since it may become so at any time.

    :param collection: the collection to check
    :param references: the collection's cross-catalogue references
    :returns: the findings found
    """
    from faint_fuzzies.site.objects import entries_without_coordinates
    entries = [Entry(unit=obj, members=collection.members_of(obj)) for obj in collection.catalogues[0].objects]
    return [Finding(e.unit.catalogue, e.unit.number, e.unit.label, ObjectAttribute.COORDINATES, ERROR,
                    "no coordinates, which the website needs for every object outside the Solar System "
                    "(a double star may take them from its WDS entry or its first pair)")
            for e in entries_without_coordinates(entries, references)]


def missing_constellation_findings(collection: Collection) -> list[Finding]:
    """An error for each own-catalogue object without a CONSTELLATION: the website shows it for every object
    that is not part of the Solar System (type S), so building it would stop there - whether or not the
    object is actually published yet, since it may become so at any time. Unlike coordinates, there is no
    fallback through the WDS or a group's pairs: a constellation is always only taken from the object's own
    record.

    :param collection: the collection to check
    :returns: the findings found
    """
    return [Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.CONSTELLATION, ERROR,
                    "no constellation, which the website needs for every object outside the Solar System")
            for obj in collection.catalogues[0].objects
            if ObjectType.SOLAR_SYSTEM not in obj.types and not obj.constellation]


def herschel_findings(collection: Collection, references: References) -> list[Finding]:
    """A Warning for each Object named like a Herschel object that has no Herschel reference.

    :param collection: the collection to check
    :param references: the collection's cross-catalogue references
    :returns: the findings found
    """
    return [Finding(obj.catalogue, obj.number, obj.label,
                    ObjectAttribute.GROUP if obj.is_group and not obj.names else ObjectAttribute.NAME, WARNING,
                    f"named {name} like a Herschel object, but no object of the Herschel catalogue has that name "
                    "(the Herschel 400 list leaves it out)")
            for obj, name in herschel_names_without_reference(collection, references)]


def group_existence_findings(collection: Collection) -> list[Finding]:
    """An Error for each double star pair of the own catalogue (see names.kind_of) whose GROUP names no
    Group Object of the same catalogue - a typo, or the Group record is missing from the file. Only a scan of
    the whole catalogue can show this, so - like a missing image file or a missing position - it marks the
    pair without making it Invalid (see CONTEXT.md: Error). A pair with several GROUP aliases (rare) needs
    only one of them to match; a pair with no GROUP at all (a lone, unpaired system needs none) is not checked.

    :param collection: the collection to check
    :returns: the findings found
    """
    findings = []
    for obj in collection.objects:
        if obj.rank != 0 or kind_of(obj) != PAIR or not obj.groups:
            continue
        if not any(collection.groups_named(obj.rank, name) for name in obj.groups):
            findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, ERROR,
                                    f"names group {', '.join(obj.groups)}, but no object of {obj.catalogue} is that "
                                    "group"))
    return findings


def orphan_group_findings(collection: Collection) -> list[Finding]:
    """An Error for each Group Object of the own catalogue that no pair's GROUP names - the mirror of
    group_existence_findings: the typo (or the missing record) is on the pair's side instead of the group's, or
    every pair that once named this group was since removed or renamed.

    :param collection: the collection to check
    :returns: the findings found
    """
    findings = []
    for obj in collection.objects:
        if obj.rank != 0 or not obj.is_group:
            continue
        if not any(collection.members_named(obj.rank, name) for name in obj.groups):
            findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, ERROR,
                                    f"is the group {', '.join(obj.groups)}, but no object of {obj.catalogue} names "
                                    "it"))
    return findings


def wds_reference_findings(collection: Collection, references: References) -> list[Finding]:
    """An Error for each own-catalogue double star pair, not marked DISABLE_WDS, whose relationship to the WDS
    is not exactly one-to-one:

    * no reference to the WDS at all (see references.wds_reference) - a typo in its name or Component, or the
      pair genuinely is not in the WDS and should be marked DISABLE_WDS instead. Much of a pair's own data
      (coordinates, magnitude, separation) usually lives only on the WDS pair it references, so a missing
      reference often means the pair itself is quietly incomplete. When the own record's own names are what
      disagree (see references.pair_wds_disagreement) - one name matching one WDS pair, another matching a
      different one, neither shared - the message says so and names both, rather than just "no reference".
    * more than one reference to the WDS - typically a typo in one of the pair's own names that happens to
      also be a real, unrelated WDS entry's name (own catalogue's problem), but sometimes the WDS itself
      attaches one alternate name to two different pairs (nothing to fix on the own catalogue's side then;
      see the "grill-with-docs" session log on 30 Peg/HJ961 vs. nu UMa/A1352 for two real examples).
    * a WDS pair referenced by more than one own-catalogue pair - a likely duplicate of one system entered
      twice, reported on each of the own pairs involved, naming the others (see duplicate_name_findings for
      the same style, for an outright identical name+Component instead of a shared WDS target).

    Nothing is reported when no WDS catalogue is loaded - there is then nothing to reference at all, own or
    otherwise.

    :param collection: the collection to check
    :param references: the collection's cross-catalogue references
    :returns: the findings found
    """
    if not any(Path(c.name).stem.casefold() == "wds" for c in collection.catalogues):
        return []
    findings = []
    claimed_by: dict[int, list[Object]] = defaultdict(list)
    for obj in collection.objects:
        if (obj.rank != 0 or obj.is_group or ObjectType.DOUBLE_STAR not in obj.types
                or obj.record.get(ObjectAttribute.DISABLE_WDS)):
            continue
        matches = [r for r in references.of(obj) if Path(r.catalogue).stem.casefold() == "wds"]
        if not matches:
            disagreement = references.pair_wds_disagreement(obj)
            if disagreement:
                parts = ", ".join(f"'{name}' matches {wds.label}" for name, wds in disagreement)
                findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.NAME, ERROR,
                                        f"double star pair's own names disagree about which WDS entry it is: "
                                        f"{parts}"))
            else:
                findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.NAME, ERROR,
                                        "double star pair has no reference to the WDS (set DISABLE_WDS if that "
                                        "is correct)"))
        elif len(matches) > 1:
            names = ", ".join(_pair_identity(m) for m in matches)
            findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.NAME, ERROR,
                                    f"double star pair matches {len(matches)} WDS entries ({names}) - a typo in "
                                    "one of its own names that happens to also be a real, unrelated WDS entry's, "
                                    "or the WDS itself gives that name to more than one entry"))
        for match in matches:
            claimed_by[id(match)].append(obj)
    for owners in claimed_by.values():
        if len(owners) < 2:
            continue
        for obj in owners:
            others = ", ".join(f"record {o.number} ({o.label})" for o in owners if o is not obj)
            findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.NAME, ERROR,
                                    f"references the same WDS entry as {others} - a likely duplicate of one "
                                    "system entered twice"))
    return findings


def constellation_findings(collection: Collection) -> list[Finding]:
    """A warning for each own-catalogue Object whose CONSTELLATION disagrees with the one astropy computes from
    its own COORDINATES (at its own EQUINOX, J2000.0 when it gives none) - a typo, or a stale value left over
    from an edited position. Objects with no CONSTELLATION or no COORDINATES are not checked (most Solar System
    objects have neither, and are not expected to name a constellation anyway); nor is an Object whose
    CONSTELLATION names none of the 88 IAU constellations at all - that is an error of its own, made Invalid
    before this ever runs (see domain.formats.constellation_error). Positions are batched into two
    astropy calls (one per EQUINOX) rather than one per object, which is what keeps this cheap. astropy (and,
    through domain.dss, numpy and PIL) is imported here rather than at module level, so that a command that
    never calls this - most of them - does not pay for loading it (see converters.ugc, which does the same).

    :param collection: the collection to check
    :returns: the findings found
    """
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    from faint_fuzzies.domain.dss import dss_coordinates

    candidates = [(obj, dss_coordinates(obj), str(obj.record.get(ObjectAttribute.EQUINOX, "J2000.0")).strip())
                  for obj in collection.catalogues[0].objects if obj.constellation]
    candidates = [(obj, coordinates, equinox) for obj, coordinates, equinox in candidates if coordinates is not None]

    def computed(group: list[tuple[Object, tuple[float, float], str]], **frame: str) -> dict[int, str]:
        if not group:
            return {}
        ra = [coordinates[0] for _obj, coordinates, _equinox in group] * u.hour
        dec = [coordinates[1] for _obj, coordinates, _equinox in group] * u.deg
        names = SkyCoord(ra, dec, **frame).get_constellation(short_name=True)
        return {id(obj): str(name) for (obj, _coordinates, _equinox), name in zip(group, names)}

    by_object = {**computed([c for c in candidates if c[2] != "B1950"], frame="icrs"),
                **computed([c for c in candidates if c[2] == "B1950"], frame="fk4", equinox="B1950")}
    return [Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.CONSTELLATION, WARNING,
                    f"constellation {obj.constellation} does not match {by_object[id(obj)]}, computed from its "
                    "own coordinates")
            for obj, _coordinates, _equinox in candidates
            if by_object[id(obj)].casefold() != obj.constellation.casefold()]


_OWN_MEDIA_ATTRIBUTES = {ObservationAttribute.SKETCH: "sketches", ObservationAttribute.PHOTOGRAPH: "photographs",
                        ObservationAttribute.IMAGE: "images"}


def own_media_findings(root: Path, objects: list[Object]) -> list[Finding]:
    """The own catalogue's SKETCH, PHOTOGRAPH and IMAGE files that are not found in their
    observations/owner/ subfolder (see datadir.owner_media_folder).

    :param root: the data directory
    :param objects: the own catalogue's objects to check
    :returns: the findings found
    """
    folders = {key: owner_media_folder(root, key) for key in OWNER_MEDIA_FOLDERS}
    findings = []
    for obj in objects:
        numbers = record_numbers(obj.record.get(ObjectAttribute.OBSERVATIONS, []))
        for observation in obj.observations:
            number = numbers.get(id(observation.record))
            for key, attribute in _OWN_MEDIA_ATTRIBUTES.items():
                folder = folders[key]
                findings.extend(Finding(obj.catalogue, obj.number, obj.label, key, ERROR,
                                        f"file '{name}' not found in {folder.name}/", number)
                                for name in missing_files(list(getattr(observation, attribute)), folder))
    return findings


def optic_names_file_findings(root: Path) -> list[Finding]:
    """A warning for optic_names.json (optional, so nothing is reported when there is no such file) when
    the file itself cannot be used. An explicit --optic-names file that cannot be used is a hard error
    instead (see datadir.read_optic_names_at) - this is only for the optional, root-relative file.

    :param root: the data directory
    :returns: the findings found
    """
    path = optic_names_file(root)
    if path is None:
        return []
    _names, why = read_optic_names(root)
    if why:
        return [Finding(path.name, 0, None, None, WARNING, f"{why}; no optic gets a name")]
    return []


def optic_name_findings(objects: list[Object], names: dict[str, str], label: str) -> list[Finding]:
    """Warnings for each optic code an observation uses that `names` gives no name for. Observations read
    from a project file are left out (see Observation.project_only).

    :param objects: the objects whose observations are checked
    :param names: the optic code -> readable name mapping, already resolved (see datadir.read_optic_names
        for the optional, root-relative file, or datadir.read_optic_names_at for an explicit --optic-names one)
    :param label: the file `names` is from, for the finding's message
    :returns: the findings found
    """
    used: dict[str, list[Any]] = {}  # optic code -> [first object, its observation number, where, count]
    for obj in objects:
        numbers = record_numbers(obj.record.get(ObjectAttribute.OBSERVATIONS, []))
        for observation in obj.all_observations:
            if observation.optic is None or observation.optic.code in names:
                continue
            if observation.project_only:
                continue
            entry = used.setdefault(observation.optic.code,
                                    [obj, numbers.get(id(observation.record)), observation.source, 0])
            entry[3] += 1
    return [Finding(obj.catalogue, obj.number, obj.label, ObservationAttribute.OPTIC, WARNING,
                    f"optic '{code}' has no name in {label} (used by {count} observation"
                    f"{'s' if count != 1 else ''}; first {'in ' + source if source else 'here'})", number)
            for code, (obj, number, source, count) in sorted(used.items())]


def object_name_abbreviation_findings(root: Path) -> list[Finding]:
    """A warning for object_name_abbreviations.json (optional, so nothing is reported when there is no such
    file) when the file itself cannot be used - unlike optic_name_findings, there is no per-usage check: a
    missing short form is not wrong, it just means that name is never found by it.

    :param root: the data directory
    :returns: the findings found
    """
    path = object_name_abbreviations_file(root)
    if path is None:
        return []
    _abbreviations, why = read_object_name_abbreviations(root)
    if why:
        return [Finding(path.name, 0, None, None, WARNING, f"{why}; no name gets a short form")]
    return []


def page_description_findings(root: Path) -> list[Finding]:
    """A warning for site/page_descriptions.json (optional, so nothing is reported when there is no such
    file) when the file itself cannot be used - as with object_name_abbreviations.json, there is no per-usage
    check: a page missing from it, or missing one of its two keys, is not wrong, it just shows none of it.

    :param root: the data directory
    :returns: the findings found
    """
    path = root / PAGE_DESCRIPTIONS_FILE
    if not path.is_file():
        return []
    _descriptions, why = read_page_descriptions(root)
    if why:
        return [Finding(PAGE_DESCRIPTIONS_FILE, 0, None, None, WARNING,
                        f"{why}; no page gets a description or an image caption")]
    return []


def duplicate_pair_findings(collection: Collection) -> list[Finding]:
    """An Error for each own-catalogue double star pair that shares a name and its Component with another pair
    of the own catalogue - the same identity claimed twice (see names.full_key, names.component_key: names are
    compared as written, without their short forms, without regard to case and spacing; a pair without a
    Component counts as AB, see names.component_of). A name together with a Component identifies one member of
    a Group (see CONTEXT.md), so two different pair records can never legitimately share both - unlike
    duplicate_name_findings below (which also covers Groups and other kinds, where a shared name is often
    legitimate: a cluster and its nebula, a shared Herschel number - which is why that one is opt-in), this
    always runs. One finding per colliding pair of records, however many of their names happen to coincide
    (two pairs sharing both their own name and the WDS id, for example, would otherwise be reported twice).

    :param collection: the collection to check
    :returns: the findings found
    """
    found: dict[tuple, list[Object]] = defaultdict(list)
    for obj in collection.objects:
        if obj.rank != 0 or kind_of(obj) != PAIR:
            continue
        written = split_names(str(obj.record.get(ObjectAttribute.NAME, "")))
        for name in dict.fromkeys(full_key(n) for n in written):
            found[(name, component_key(component_of(obj)))].append(obj)
    colliding: dict[int, set[int]] = defaultdict(set)
    by_id: dict[int, Object] = {}
    for holders in found.values():
        if len(holders) < 2:
            continue
        for obj in holders:
            by_id[id(obj)] = obj
            colliding[id(obj)].update(id(other) for other in holders if other is not obj)
    findings = []
    for obj_id, other_ids in colliding.items():
        others = sorted((by_id[oid] for oid in other_ids), key=lambda o: o.number)
        names = ", ".join(f"record {o.number} ({o.label})" for o in others)
        obj = by_id[obj_id]
        findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.NAME, ERROR,
                                f"has the same name and Component as {names} - probably a duplicate record"))
    return sorted(findings, key=lambda p: p.record)


def _pair_identity(obj: Object) -> str:
    """A pair's label, with its written Component appended when it has one, so that pairs sharing a name (a
    group of pairs catalogued together under one designation) can still be told apart in a list.

    :param obj: the pair
    :returns: "label" or, when the record gives a Component, "label COMPONENT"
    """
    component = component_name(obj)
    return f"{obj.label} {component}" if component else obj.label


def _has_own_content(obj: Object) -> bool:
    """Whether this Object's own record carries an own observation (a real one or a Header, either counts,
    since both live in OBSERVATIONS) or a NOTES remark. Never a community-attached observation from another
    observer: those can equally attach to the matching WDS pair directly (attach.py searches the own
    catalogue first, not instead of the WDS), so they are not lost if the own Object goes away - see
    redundant_group_findings, the one check this distinction matters for.

    :param obj: the Object to check
    :returns: whether it has own content
    """
    return bool(obj.record.get(ObjectAttribute.OBSERVATIONS)) or bool(
        str(obj.record.get(ObjectAttribute.NOTES, "")).strip())


_WDS_ID = re.compile(r"^WDS\d{5}[+-]\d{4}$", re.IGNORECASE)


def redundant_group_findings(collection: Collection, references: References) -> list[Finding]:
    """An Info for each own-catalogue double star Group whose own pairs, one for one, exactly match pairs of
    one WDS group - never a Warning or an Error, since none of the three cases below changes or breaks
    anything by itself, they only note a fact about the data and (except the third) suggest an action. Own
    names and WDS names are compared with names.full_key, not names.literal_key: the WDS always abbreviates
    Greek letters, "zet Boo", the own catalogue always spells them out, "zeta Boo", and that difference must
    not by itself make either side look like it carries a name the other lacks.

    * every one of the WDS group's own pairs is covered (a pure mirror, adding nothing of the user's own over
      what the WDS already has), the own Group carries no name of its own the WDS group lacks, and neither the
      Group record nor any of its member pairs has any own content (see _has_own_content: an observation from
      another observer does not count, and does not need the own Group to keep showing on the website either,
      since it would simply attach to the matching WDS pair directly instead) - removing it is recommended,
      since nothing on the site would change: the WDS already has every one of its pairs, under the same
      names;
    * only part of the WDS group's own pairs are covered (a Group that tracks *some* of a larger WDS system,
      to limit what the website shows), again no own name the WDS group lacks, and again no own content
      anywhere in the Group or its pairs - removing it is an option worth considering, but not a no-op like
      the first case: the WDS pairs it currently leaves out would then start showing on the site, which is a
      real change;
    * only part of the WDS group's own pairs are covered, but the own Group *does* carry a name of its own
      the WDS group lacks (a nickname, a Bayer designation the WDS never recorded) - removing it would lose
      that name, so instead this suggests completing it: add the pairs it is still missing. Since no removal
      is suggested here, the Group or its pairs may freely carry own content (a Header, an observation) - that
      restriction only matters for the first two cases, where removal is actually on the table.

    A fourth combination - full coverage, but an own name the WDS group lacks - is left unreported entirely:
    removing it would be the only point of saying anything, and that would cost the one thing only the own
    record carries.
    Independently of all four (even the unreported fourth, and regardless of own content, for the same reason
    as the third case - no removal is suggested), a WDS group may itself carry a name - a cross-catalogue
    designation, typically - that the own Group's record does not have at all; that is its own Info,
    suggesting the name be added, whatever the pair coverage. The WDS group's own identifier (its
    "WDSnnnnn+nnnn" name, always present on the WDS side and essentially never duplicated into the own
    catalogue, see CONTEXT.md "WDS id") does not count for this: every own Group would otherwise always seem
    to be missing it.
    In every case, every member pair must have exactly one reference to the WDS (see wds_reference_findings) -
    a Group with a member that is not resolved to the WDS at all is left unreported, whatever its coverage,
    since nothing can be said about how it compares to the WDS group until that is fixed.
    Nothing is reported when no WDS catalogue is loaded.

    :param collection: the collection to check
    :param references: the collection's cross-catalogue references
    :returns: the findings found
    """
    if not any(Path(c.name).stem.casefold() == "wds" for c in collection.catalogues):
        return []
    findings = []
    for obj in collection.objects:
        if obj.rank != 0 or not obj.is_group or ObjectType.DOUBLE_STAR not in obj.types:
            continue
        members = collection.members_of(obj)
        if not members:
            continue
        wds_groups = [r for r in references.of(obj) if Path(r.catalogue).stem.casefold() == "wds"]
        if not wds_groups:
            continue
        wds_group = wds_groups[0]
        own_wds_refs = [wds_reference(m, references) for m in members]
        if any(r is None for r in own_wds_refs):
            continue
        referenced = {id(r) for r in own_wds_refs}
        if len(referenced) != len(members):
            continue
        wds_member_ids = {id(m) for m in collection.members_of(wds_group)}
        if not referenced <= wds_member_ids:
            continue
        own_names_raw = obj.names or obj.groups
        wds_names_raw = wds_group.names or wds_group.groups
        own_keys = {full_key(n) for n in own_names_raw}
        wds_keys = {full_key(n) for n in wds_names_raw}
        own_names_known = own_keys <= wds_keys
        no_own_content = not _has_own_content(obj) and not any(_has_own_content(m) for m in members)
        if referenced == wds_member_ids:
            if own_names_known and no_own_content:
                findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, INFO,
                                        f"matches the WDS group {wds_group.label} exactly and has no observation "
                                        "or note of its own anywhere in it - removing it is recommended, nothing "
                                        "on the site would change, the WDS already has every one of its pairs"))
        else:
            missing = ", ".join(_pair_identity(m) for m in collection.members_of(wds_group)
                                if id(m) not in referenced)
            if own_names_known:
                if no_own_content:
                    findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, INFO,
                                            f"covers {len(referenced)} of the {len(wds_member_ids)} pairs of the "
                                            f"WDS group {wds_group.label}, matching them exactly - removing it is "
                                            f"an option, but the WDS's other pair(s) ({missing}) would then start "
                                            "showing on the site, which is a real change"))
            else:
                findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, INFO,
                                        f"covers {len(referenced)} of the {len(wds_member_ids)} pairs of the WDS "
                                        f"group {wds_group.label}, matching them exactly, but also carries its "
                                        "own name the WDS group does not have - consider adding its missing "
                                        f"pair(s) ({missing}) instead of removing it"))
        wds_extra = [n for n in wds_names_raw if not _WDS_ID.match(n.strip()) and full_key(n) not in own_keys]
        if wds_extra:
            names = ", ".join(dict.fromkeys(wds_extra))
            findings.append(Finding(obj.catalogue, obj.number, obj.label, ObjectAttribute.GROUP, INFO,
                                    f"the WDS group {wds_group.label} also carries the name {names}, which this "
                                    "Group's own record does not have - consider adding it"))
    return findings


def duplicate_name_findings(collection: Collection) -> list[Finding]:
    """A warning for each Object that shares a name with another Object of its catalogue. Two Objects only share a
    name when they are of one kind (group, pair, other) and, for pairs, have the same component; the names are
    compared as they are written, without their short forms, and without regard to case and spacing. Many are
    meant (the cluster and the nebula of one NGC number, a nickname of two Objects, the number of a Herschel object
    that two galaxies share), which is why this is a report of its own and no part of loading.

    :param collection: the collection to check
    :returns: the findings found
    """
    findings: list[Finding] = []
    for catalogue in collection.catalogues:
        found: dict[tuple, list[tuple[str, Object]]] = defaultdict(list)
        for obj in catalogue.objects:
            kind = kind_of(obj)
            attribute = ObjectAttribute.GROUP if obj.is_group else ObjectAttribute.NAME
            written = split_names(str(obj.record.get(attribute, "")))
            for name in dict.fromkeys(full_key(n) for n in written):
                found[(kind, name, component_key(component_of(obj)) if kind == PAIR else None)].append((attribute, obj))
        for (_kind, _name, _component), holders in found.items():
            if len(holders) < 2:
                continue
            for attribute, obj in holders:
                others = ", ".join(f"record {o.number} ({o.label})" for _a, o in holders if o is not obj)
                shown = next(n for n in split_names(str(obj.record.get(attribute, ""))) if full_key(n) == _name)
                findings.append(Finding(obj.catalogue, obj.number, obj.label, attribute, WARNING,
                                        f"the name '{shown}' is also the name of {others}"))
    return sorted(findings, key=lambda p: (p.catalogue, p.record))
