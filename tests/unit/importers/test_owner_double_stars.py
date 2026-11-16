"""The own catalogue's double-star attach-records (importers/owner_double_stars.py), the Alternative-names file
(importers/wds_alternative_names.py) and how both feed attach.py's matching, in a loaded data directory (see
CONTEXT.md, "Own catalogue" and "Alternative name"). The objects and findings are the ones filter and validate show.

Fixture "double_star_attach_datadir": a WDS catalogue with a group (eps Aql, WDS19000+1000) of two pairs (STFX1 AB,
STFX2 AC) and two standalone pairs (STFY3, STFZ4); an own catalogue with one plain deep-sky object (ZZZ Deep Sky
Object), an attach-record for STFX1 (an observation plus a NOTES tag), one for STFX2 (an observation with a missing
sketch file), one matching nothing ("No Such Star"), one with no NAME at all, one reachable only through an
Alternative name ("Zeta Mystery", for STFY3), and one DISABLE_WDS double star kept independent; an Alternative-names
file giving STFY3 "Zeta Mystery", replacing eps Aql's own names with "Old Catalog Name" (keeping its WDS id), and
rejecting an entry that tries to target STFX1 (a pair of a group) directly; one giving STFZ4 "Z4 Informal Name"
alongside a second, non-matching name ("Nonexistent Designation"); one Global-scope observer (dana-example) with a
community row on STFZ4, which otherwise has no own-catalogue record at all; STFW5 with one private
(DATE/TIME-bearing) observation and a sessions.json with the one session it falls inside; STFV6, named alongside a
second, non-matching name ("Nonexistent Double Star Name") directly on its own attach-record, rather than through an
Alternative name; two unrelated standalone pairs that happen to share one name ("Shared Name"): STFU7 (an explicit
AB) and STFU8 (no given component, so it counts as ab too) - an attach-record for STFU7, named alongside "Shared
Name", so that second name is itself ambiguous, not simply unmatched; one giving eps Aql's AC pair (STFX2) "Eps Aql
C" by Component, without reaching the Group or its AB pair; one rejected for giving a Component on an
already-ungrouped pair (STFY3); one rejected for giving eps Aql a Component none of its pairs have. A second Group,
WDS08000+0800, has two pairs (STFV9 AB, STFV10 AC) sharing no name but their WDS id - an Alternative-names entry
gives STFV9's own pair a name by its own designation ("STFV9") plus the WDS id and a Component, to check that
"STFV9" is not itself flagged as unmatched, even though build_name_index deliberately leaves a grouped pair's own
names out of its lookup. Two further entries both give STFW5 alternative names ("First Informal Name", "Second
Informal Name"), to check that addressing the same pair twice is flagged."""

import pytest

from faint_fuzzies.domain.filters import FilterSpec, filter_objects
from tests.unit.builders import FIXTURES, load_world


@pytest.fixture(scope="module")
def world():
    """The objects with their observations, as filter shows them, and the findings, as validate reports them."""
    data = load_world(FIXTURES / "double_star_attach_datadir")
    matches = filter_objects(data.collection, FilterSpec.from_dict({}), data.references, data.observers)
    return {"objects": [(m.object, [f.observation for f in m.observations]) for m in matches],
            "findings": data.findings.all}


def _object(world, name):
    """The one object whose names or groups include `name`, and its observations."""
    found = [(o, observations) for o, observations in world["objects"] if name in o.names or name in o.groups]
    assert len(found) == 1, f"looking for {name!r}"
    return found[0]


def _group(world, name):
    """The one Group (no names of its own) whose groups include `name`; unlike _object, not one of its pairs, which
    may share one of its names."""
    found = [o for o, _observations in world["objects"] if not o.names and name in o.groups]
    assert len(found) == 1, f"looking for {name!r}"
    return found[0]


def _finding(world, text):
    """The one finding whose message contains `text`."""
    found = [f for f in world["findings"] if text in f.message]
    assert len(found) == 1, f"looking for {text!r}"
    return found[0]


def test_an_attach_record_merges_its_observation_and_tags_onto_the_matched_pair(world):
    """STFX1's observation and NOTES tag land on the WDS pair's own record and observations, not as a separate
    own-catalogue Object and not as a community observation."""
    pair, observations = _object(world, "STFX1")
    assert pair.catalogue == "wds.json"
    assert pair.record["NOTES"] == "Private note"
    assert len(observations) == 1
    assert observations[0].observer is None
    assert observations[0].record["DESCRIPTION"] == "Clean split"


def test_a_record_with_no_name_is_an_error(world):
    finding = _finding(world, "has no NAME")
    assert finding.catalogue == "objects.json"
    assert finding.severity == "error"


def test_a_record_matching_nothing_is_rejected(world):
    assert _finding(world, "no double star named 'No Such Star'").object == "No Such Star"
    assert "No Such Star" not in [n for o, _observations in world["objects"] for n in o.names]


def test_an_alternative_name_lets_a_record_match_its_pair(world):
    """"Zeta Mystery" is not a WDS name at all - it only matches STFY3 because wds_alternative_names.json merged it on
    before attach_owner_double_stars ran. Added alongside, not replacing - so the WDS id must still be last."""
    pair, observations = _object(world, "STFY3")
    assert list(pair.names) == ["STFY3", "Zeta Mystery", "WDS14000+1500"]
    assert len(observations) == 1
    assert observations[0].record["DESCRIPTION"] == "Found via its alternative name"


def test_an_alternative_name_cannot_target_a_pair_of_a_group(world):
    """STFX1 belongs to the eps Aql group, so it is not a valid Alternative-names target (see
    wds_alternative_names.py's module docstring) - the entry is rejected, not silently ignored."""
    assert _finding(world, "no double star named 'STFX1'").catalogue == "wds_alternative_names.json"
    assert "Should Not Apply" not in _object(world, "STFX1")[0].names


def test_a_component_narrows_an_alternative_name_to_one_pair_of_the_group(world):
    """"eps Aql" plus component AC targets STFX2 specifically (the way "Mizar & Alcor" would target one pair of the
    zeta UMa Group) - the new name lands on STFX2 only, not on the Group and not on its sibling pair STFX1."""
    assert "Eps Aql C" in _object(world, "STFX2")[0].names
    assert "Eps Aql C" not in _object(world, "STFX1")[0].names
    assert "Eps Aql C" not in _group(world, "WDS19000+1000").groups


def test_a_grouped_pairs_own_name_is_not_flagged_as_unmatched_once_a_component_narrows_to_it(world):
    """"STFV9" is only ever a name of its own pair, never of the WDS08000+0800 Group (build_name_index deliberately
    leaves a grouped pair's own names out of its lookup). Giving "STFV9, WDS08000+0800" with component AB must not
    warn about "STFV9" not matching anything: it is exactly the name the component resolves to."""
    assert [f for f in world["findings"] if "'STFV9'" in f.message] == []
    assert "Test Informal Name" in _object(world, "STFV9")[0].names
    assert "Test Informal Name" not in _object(world, "STFV10")[0].names


def test_two_entries_addressing_the_same_pair_are_both_flagged(world):
    """Both entries are applied (it is not an error), but each gets a warning naming the other, since this is normal
    when deliberately splitting names across entries but just as easily an accidental duplicate."""
    names = _object(world, "STFW5")[0].names
    assert "First Informal Name" in names
    assert "Second Informal Name" in names
    assert _finding(world, "addresses the same pair (STFW5) as line 10").severity == "warning"
    assert _finding(world, "addresses the same pair (STFW5) as line 9").severity == "warning"


def test_a_component_is_rejected_on_an_already_ungrouped_pair(world):
    """STFY3 has no Group to narrow from, so a component makes no sense on it."""
    assert _finding(world, "is not a Group; 'component' does not apply").catalogue == "wds_alternative_names.json"
    assert "Should Not Apply Either" not in _object(world, "STFY3")[0].names


def test_a_component_none_of_the_groups_pairs_have_is_also_rejected(world):
    """Not applied to the Group as a whole, which would defeat the point of narrowing it to one pair."""
    assert _finding(world, "has no pair with component ZZ").catalogue == "wds_alternative_names.json"
    assert "Should Not Apply At All" not in _group(world, "WDS19000+1000").groups


def test_one_non_matching_name_alongside_a_matching_one_is_a_warning_not_an_error(world):
    """"Nonexistent Designation" matches nothing, but "STFZ4" still resolves the entry - it is applied in full, with
    only a warning about the other name."""
    finding = _finding(world, "'Nonexistent Designation' does not match any double star")
    assert finding.catalogue == "wds_alternative_names.json"
    assert finding.severity == "warning"
    assert "Z4 Informal Name" in _object(world, "STFZ4")[0].names


def test_one_non_matching_name_on_an_attach_record_itself_is_also_a_warning_not_an_error(world):
    """The same rule for a name given directly on an attach-record (match_any_name): the warning carries that name's
    own reason (matcher.find's message), downgraded to a warning."""
    finding = _finding(world, "no double star named 'Nonexistent Double Star Name'")
    assert finding.catalogue == "objects.json"
    assert finding.severity == "warning"
    assert _object(world, "STFV6")[1][0].record["DESCRIPTION"] == "Found despite one bad name"


def test_a_name_that_is_itself_ambiguous_is_also_just_a_warning_not_a_false_no_match(world):
    """"Shared Name" alone matches two pairs (STFU7's explicit AB and STFU8's ab-by-default). The warning must say so,
    not claim the name matches nothing, which would be misleading about what is wrong."""
    finding = _finding(world, "'Shared Name' with component AB matches 2 pairs")
    assert finding.catalogue == "objects.json"
    assert finding.severity == "warning"
    assert _object(world, "STFU7")[1][0].record["DESCRIPTION"] == "Found despite an ambiguous second name"


def test_replace_drops_the_matched_systems_own_names_but_its_wds_id(world):
    """Both the parsed groups (used for matching, and by the app) and the record's own GROUP (used by the website's
    get_display_names) - a merge must keep both in sync, or the site would keep showing "eps Aql"."""
    group = _group(world, "WDS19000+1000")
    assert list(group.groups) == ["Old Catalog Name", "WDS19000+1000"]
    assert group.record["GROUP"] == "Old Catalog Name, WDS19000+1000"


def test_a_groups_new_name_is_also_added_to_each_of_its_own_pairs_and_its_dropped_name_removed_from_them_too(world):
    """STFX1 keeps its own designation; only "eps Aql", the name the replace dropped from the Group, is dropped from
    the pair too, with the WDS id still last - in the names and in the record's own NAME (website display)."""
    pair, _observations = _object(world, "STFX1")
    assert list(pair.names) == ["STFX1", "Old Catalog Name", "WDS19000+1000"]
    assert pair.record["NAME"] == "STFX1, Old Catalog Name, WDS19000+1000"


def test_a_disable_wds_record_stays_an_independent_object(world):
    assert _object(world, "IndependentDouble")[0].catalogue == "objects.json"


def test_a_missing_sketch_on_an_attach_records_observation_is_still_reported(world):
    """The finding names the WDS pair the observation was attached to (see checks.py own_media_findings)."""
    finding = _finding(world, "missing_sketch.jpg")
    assert finding.object == "STFX2"
    assert finding.catalogue == "wds.json"
    assert finding.attribute == "SKETCH"


def test_a_private_observation_on_an_attach_record_is_assigned_its_session(world):
    """Without it, the observation is missing from the Browse page's session filter and session list and from the
    Statistics page's counts per location, which all read Observation.session (see domain.catalogue.assign_sessions
    and importers.owner_double_stars.read_owner_double_stars)."""
    _pair, observations = _object(world, "STFW5")
    assert len(observations) == 1
    assert observations[0].public is False
    assert observations[0].session.start.isoformat(timespec="minutes") == "2011-10-02T22:00"
