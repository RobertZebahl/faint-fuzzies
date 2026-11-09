"""The criteria about an Object itself (domain/filters.py), against the fixture catalogue objects.json in the common
format. Every case names the filter, as a user writes it, and the first names of the Objects that must come back, in
catalogue order."""
import pytest

from tests.unit.builders import FIXTURES, filter_cases, filter_labels

OBJECTS = FIXTURES / "objects.json"


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{}', "3C48", "H1.1", "NGC752", "Mond", "78P/Gehrels", "2 Sge", "HDS2753", "STFA41", "STF1884"),
))
def test_empty_filter_matches_every_object(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"name": "NGC1055"}', "H1.1"),
    ('{"name": "ngc1055"}', "H1.1"),
    ('{"name": "NGC105"}',),
    ('{"name": ["3C48", "ngc752"]}', "3C48", "NGC752"),
))
def test_name_matches_exactly_and_ignores_case(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"name": "Moon"}', "Mond"),
    ('{"name": "mond"}', "Mond"),
))
def test_every_language_variant_of_a_name_matches(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"group": "2 sge"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"group": "400"}', "H1.1"),
))
def test_group_filter_matches_the_group_and_its_members(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"name_group": "NGC1055"}', "H1.1"),
    ('{"name_group": "2 sge"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"name_group": ["NGC1055", "2 sge"]}', "H1.1", "2 Sge", "HDS2753", "STFA41"),
))
def test_name_group_matches_whichever_an_object_actually_has(spec, expected):
    """name_group matches a value against either names or groups, exact and case-insensitive, like name_group_pattern
    but without needing a regular expression."""
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"type": "gx"}', "H1.1"),
    ('{"type": ["Gx", "OC"]}', "H1.1", "NGC752"),
    ('{"type": "S"}', "Mond", "78P/Gehrels"),
))
def test_type_filter_matches_any_listed_type_ignoring_case(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"type": ["Gx", "OC"], "type_exclude": "OC"}', "H1.1"),
    ('{"type": ["Gx", "OC"], "type_exclude": ["gx"]}', "NGC752"),
    ('{"type": ["S", "Q"], "type_exclude": "S"}', "3C48"),
))
def test_type_exclude_works_for_multi_character_codes(spec, expected):
    """Multi-character type codes, such as OC or Gx, match as whole codes."""
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"constellation": "sge"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"constellation": ["Cet", "and"]}', "H1.1", "NGC752"),
))
def test_constellation_filter_ignores_case(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"name_pattern": "NGC10.*"}', "H1.1"),
    ('{"name_pattern": "ngc10"}',),
    ('{"name_pattern": ["3C.*", "STF1.*"]}', "3C48", "STF1884"),
    ('{"group_pattern": "2 .*"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"constellation_pattern": "S.*"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"constellation_pattern": "[ac].*"}', "H1.1", "NGC752"),
    ('{"name_pattern": "H1[.].*", "type": "Gx"}', "H1.1"),
))
def test_patterns_are_case_insensitive_regular_expressions_that_match_completely(spec, expected):
    """name_pattern, group_pattern and constellation_pattern are regular expressions."""
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"name_group_pattern": "H1[.].*"}', "H1.1"),
    ('{"name_group_pattern": "2 .*"}', "2 Sge", "HDS2753", "STFA41"),
    ('{"name_group_pattern": "H1[.].*|2 .*"}', "H1.1", "2 Sge", "HDS2753", "STFA41"),
))
def test_name_group_pattern_matches_whichever_an_object_actually_has(spec, expected):
    """name_group_pattern matches a name or a group with the one pattern - H1.1 (no group of its own) by name, 2 Sge and
    its members (sharing its group) by group, without needing name_pattern and group_pattern both given to find either
    kind."""
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"type": "Gx", "constellation": "Cet"}', "H1.1"),
    ('{"type": "Gx", "constellation": "And"}',),
))
def test_criteria_are_combined_with_and(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"is_group": true}', "2 Sge"),
    ('{"is_group": false, "constellation": "Sge"}', "HDS2753", "STFA41"),
))
def test_is_group_selects_group_records(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected


@pytest.mark.parametrize(("spec", "expected"), filter_cases(
    ('{"type": "**"}', "2 Sge", "HDS2753", "STFA41", "STF1884"),
    ('{"type": "**", "exclude_group_members": true}', "2 Sge", "STF1884"),
    ('{"group": "400", "exclude_group_members": true}', "H1.1"),
))
def test_excluding_group_members_only_affects_members_of_double_star_groups(spec, expected):
    assert filter_labels(spec, OBJECTS) == expected
