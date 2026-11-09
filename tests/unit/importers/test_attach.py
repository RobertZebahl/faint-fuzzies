"""How a double star row of an observer's file finds its pair or group from its name and component
(importers/attach.py). A component of "*" means more than one component was observed; without a component, or with
one that matches no pair exactly, the row is attached anyway as long as the name is unambiguous (with a warning
suggesting "*", or an info when a name alone lands on a pair whose component is not the trivial AB), and is an error
only when it is not. A row's name may also be a comma-separated list of several names for the same double star; any
one matching is enough, with a warning for each other name that matches nothing.

The own catalogue of the fixture "component_datadir": the group SYS1 with the pairs AAA1 (ab) and BBB2 (cd), the
single pairs SOLO3 (ab) and SOLO4 (ab-c), PLAIN7 without any component (it counts as ab), TWIN8 with two pairs and no
group, JOIN9A (ab) and JOIN9B (ac) in the joined group JOIN9A & JOIN9B, and MULTI6 with the pairs a-bc and ab-c in the
group G6.
"""
from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import component_of
from faint_fuzzies.domain.observer import load_observers
from faint_fuzzies.importers.attach import CommunitySource, attach_community
from tests.unit.builders import FIXTURES

OBSERVATIONS = FIXTURES / "component_datadir" / "observations"


def _attach(tmp_path, *rows, file_format="project-double-stars-visual", observer="anna-example",
            file_name="visual.csv"):
    """Attaches the rows of one observer's file to a fresh copy of the own catalogue. Returns {line: (label of the
    Object, its component or None for a group)} of the attached rows, and the findings as (severity, message)."""
    folder = tmp_path / observer
    folder.mkdir(parents=True)
    (folder / file_name).write_text("".join(row + "\n" for row in rows), encoding="utf-8")
    collection = Collection([load_catalogue(OBSERVATIONS / "owner" / "objects.json")])
    result = attach_community(collection, load_observers(OBSERVATIONS / "observers.json"),
                              [CommunitySource(file_format, observer, folder / file_name)])
    attached = {int(o.source.rsplit(":", 1)[1]): (obj.label, None if obj.is_group else component_of(obj))
                for obj in collection.objects for o in obj.community_observations}
    return attached, [(f.severity, f.message) for f in result.findings]


def _row(tmp_path, name, component):
    """Attaches one visual row of a project observer; returns the Object it went to (as in _attach, None when it
    was left out) and its findings by severity."""
    attached, findings = _attach(tmp_path, f"{name};{component};;150;;;A row;;")
    by_severity = {}
    for severity, message in findings:
        by_severity.setdefault(severity, []).append(message)
    return attached.get(1), by_severity


def _the(messages):
    """The one message of a row (a row never gets two findings of one severity)."""
    (message,) = messages
    return message


def test_the_letters_of_a_component_are_unordered(tmp_path):
    """BA is the pair ab: attached without a word."""
    target, findings = _row(tmp_path, "SOLO3", "BA")
    assert target == ("SOLO3", "ab")
    assert "warning" not in findings


def test_a_comma_is_not_a_hyphen_but_the_name_is_unambiguous(tmp_path):
    """AB,C is not the component ab-c, so the exact match fails; SOLO4 names one pair, so the row is attached to it
    anyway, with a warning."""
    target, findings = _row(tmp_path, "SOLO4", "AB,C")
    assert target == ("SOLO4", "ab-c")
    assert "'SOLO4' has no component AB,C (its pair is ab-c); attached to it anyway" in _the(findings["warning"])


def test_a_mismatched_component_is_attached_anyway_when_unambiguous(tmp_path):
    """ABC matches no pair of SOLO3 exactly, but SOLO3 names only the one pair."""
    target, findings = _row(tmp_path, "SOLO3", "ABC")
    assert target == ("SOLO3", "ab")
    assert "'SOLO3' has no component ABC (its pair is ab); attached to it anyway" in _the(findings["warning"])


def test_a_system_component_goes_to_the_group(tmp_path):
    """SYS1 is a group without the component A-BC: the row is attached to the group, with a warning naming its pairs
    and suggesting "*"."""
    target, findings = _row(tmp_path, "SYS1", "A-BC")
    assert target == ("SYS1", None)
    assert "attached to the group SYS1 (AAA1, BBB2), give '*' to say so explicitly" in _the(findings["warning"])


def test_the_warning_names_the_pair_of_the_same_system_that_has_the_component(tmp_path):
    """AAA1 is the pair ab, its system's other pair BBB2 is cd: the row stays with the name and asks whether the name
    or the component was wrong."""
    target, findings = _row(tmp_path, "AAA1", "CD")
    assert target == ("AAA1", "ab")
    warning = _the(findings["warning"])
    assert "The pair BBB2 (cd) of the same system has that component" in warning
    assert "was the name or the component wrong?" in warning


def test_a_mismatched_component_with_no_sibling_is_attached_anyway(tmp_path):
    """CD matches no pair of SOLO3, and SOLO3 has no system to look for a sibling in either; the name still
    identifies the one pair, so the row goes there."""
    target, findings = _row(tmp_path, "SOLO3", "CD")
    assert target == ("SOLO3", "ab")
    assert "'SOLO3' has no component CD (its pair is ab); attached to it anyway" in _the(findings["warning"])


def test_the_structure_of_a_component_is_kept(tmp_path):
    """AB-C is the pair ab-c, not a-bc; C-AB is the same pair with its parts the other way round."""
    attached, findings = _attach(tmp_path, "MULTI6;AB-C;;150;;;A row;;", "MULTI6;C-AB;;150;;;A row;;")
    assert attached == {1: ("MULTI6", "ab-c"), 2: ("MULTI6", "ab-c")}
    assert not findings


def test_a_pair_without_a_component_is_said_to_count_as_ab(tmp_path):
    """The catalogue names no component for PLAIN7, so the warning must not claim that it has ab."""
    target, findings = _row(tmp_path, "PLAIN7", "CD")
    assert target == ("PLAIN7", "ab")
    assert ("'PLAIN7' has no component CD (its pair has no component, so it counts as ab)"
            in _the(findings["warning"]))


def test_several_pairs_of_no_one_system_are_an_error(tmp_path):
    """TWIN8 names two unrelated pairs (ab and ac) and there is no group: which one is meant is not for the importer
    to guess."""
    target, findings = _row(tmp_path, "TWIN8", "AD")
    assert target is None
    assert _the(findings["error"]) == "'TWIN8' has no pair with component AD (it has ab, ac)"


def test_the_pair_ab_wins_over_a_part_of_a_joined_group_name(tmp_path):
    """JOIN9A is the pair ab and also a part of the group JOIN9A & JOIN9B: without a component the row goes to the
    pair, silently (ab is the trivial component); the joined name itself is the group, which gets the usual "use '*'"
    warning since it was named with no component."""
    target, findings = _row(tmp_path / "pair", "JOIN9A", "")
    assert target == ("JOIN9A", "ab")
    assert "warning" not in findings
    target, findings = _row(tmp_path / "group", "JOIN9A & JOIN9B", "")
    assert target == ("JOIN9A & JOIN9B", None)
    assert "give '*' to say so explicitly" in _the(findings["warning"])


def test_a_name_alone_landing_on_a_non_trivial_component_is_an_info(tmp_path):
    """JOIN9B is the pair ac, and part of a joined group name: a row without a component still goes to the pair,
    with an info (ac is not the trivial ab) rather than a warning."""
    target, findings = _row(tmp_path, "JOIN9B", "")
    assert target == ("JOIN9B", "ac")
    assert "warning" not in findings
    assert "'JOIN9B' is the pair ac" in _the(findings["info"])


def test_a_global_observers_row_now_follows_the_same_rule_as_a_project_row(tmp_path):
    """The rows of a Global observer without a component used to go to the pair only when it was AB; that carve-out
    is gone, so JOIN9B (ac) goes to its own pair just like a project row does, with the same info, and JOIN9A (ab)
    goes to its pair silently."""
    attached, findings = _attach(tmp_path, "JOIN9B;;DS;10x50;;;;A row;;;;", "JOIN9A;;DS;10x50;;;;A row;;;;",
                                 file_format="global", observer="dana-example", file_name="global.csv")
    assert attached == {1: ("JOIN9B", "ac"), 2: ("JOIN9A", "ab")}
    (severity, message), = findings
    assert severity == "info"
    assert "'JOIN9B' is the pair ac" in message


def test_a_pair_name_wins_over_a_joined_group_name_in_the_fallback_too(tmp_path):
    """JOIN9B is the pair ac and part of the joined group JOIN9A & JOIN9B; the component A-B-C does not match
    anything, but JOIN9B still names one pair on its own, so the row goes there, not the system."""
    target, findings = _row(tmp_path, "JOIN9B", "A-B-C")
    assert target == ("JOIN9B", "ac")
    assert "'JOIN9B' has no component A-B-C (its pair is ac); attached to it anyway" in _the(findings["warning"])


def test_a_name_of_several_pairs_without_a_matching_component_goes_to_their_group(tmp_path):
    target, findings = _row(tmp_path, "MULTI6", "A-B-C")
    assert target == ("G6", None)
    assert "attached to the group G6 (MULTI6), give '*' to say so explicitly" in _the(findings["warning"])


def test_a_star_on_a_pair_of_a_group_goes_to_the_group_silently(tmp_path):
    """"*" says more than one component was seen, so the row goes to AAA1's group SYS1 directly - this is the
    expected use of "*", so there is no warning."""
    target, findings = _row(tmp_path, "AAA1", "*")
    assert target == ("SYS1", None)
    assert "warning" not in findings


def test_a_star_on_a_pair_with_no_group_is_attached_anyway_with_a_warning(tmp_path):
    """SOLO3 is a lone pair in no group: "*" has nothing bigger to attach to, so the row stays on the pair."""
    target, findings = _row(tmp_path, "SOLO3", "*")
    assert target == ("SOLO3", "ab")
    assert ("'*' on 'SOLO3' names one pair with no group of its own; attached to it anyway"
            in _the(findings["warning"]))


def test_a_component_found_only_on_a_joined_group_sibling_is_attached_there_with_a_warning(tmp_path):
    """JOIN9A is the pair ab; its component AC matches no pair of that name, but JOIN9A is also part of the joined
    group name, whose other pair JOIN9B is ac - the row goes to JOIN9B, with a warning: finding a match this way could
    equally be a typo in the name or in the component, unlike an exact match on the pair actually named."""
    target, findings = _row(tmp_path, "JOIN9A", "AC")
    assert target == ("JOIN9B", "ac")
    warning = _the(findings["warning"])
    assert "'JOIN9A' has no pair with component AC, but its group's pair JOIN9B does" in warning
    assert "was the name or the component wrong?" in warning


def test_several_pairs_of_no_one_system_with_no_component_given_are_also_an_error(tmp_path):
    """Unlike with a component, the row never reaches the "has no pair with component" check and hits the plain
    ambiguous-name case instead, asking for the component."""
    target, findings = _row(tmp_path, "TWIN8", "")
    assert target is None
    assert _the(findings["error"]) == "'TWIN8' matches 2 pairs; give the component"


def test_a_name_given_as_a_comma_separated_list_attaches_on_the_one_that_matches(tmp_path):
    """SOLO3 matches its pair exactly, so the row attaches there, with only a warning about the other name - carrying
    that name's own reason for not matching."""
    target, findings = _row(tmp_path, "SOLO3, Nonexistent Double Star Name", "AB")
    assert target == ("SOLO3", "ab")
    assert "no double star named 'Nonexistent Double Star Name'" in _the(findings["warning"])
