"""A double star pair's component fields on the website (site/objects.py: get_pair_component,
_double_star_components) and a group member's magnitude/size (_group_member): all passed through raw, for the template
to format itself (see README.md's "Formatting raw values"). SEPARATION/POSITION_ANGLE/YEAR are checked with
`is not none` by the template rather than truthiness, so a real position angle of 0 degrees is not mistaken for a
missing one."""
from faint_fuzzies.domain.model import Object, ObjectAttribute
from faint_fuzzies.site.objects import SiteData, _double_star_components, _group_member, get_pair_component


def _pair(component=""):
    return Object(record={ObjectAttribute.COMPONENT: component}, names=("Pair",), groups=(), types=(),
                  constellation="")


def _component_fields(component):
    """The one entry _double_star_components builds for a single pair with this COMPONENT."""
    row = {}
    _double_star_components(row, [_pair(component)], "en", SiteData(), True)
    return row["DOUBLESTAR_COMPONENTS"][0]


def test_a_pairs_component_is_split_into_name_separation_angle_and_year():
    component = get_pair_component(_pair("AB,3.9,165,2021"), SiteData())
    assert component["name"] == "AB"
    assert component["separation"] == 3.9
    assert component["angle"] == 165
    assert component["year"] == 2021


def test_a_missing_component_is_all_none():
    component = get_pair_component(_pair(""), SiteData())
    assert component["name"] is None
    assert component["separation"] is None
    assert component["angle"] is None
    assert component["year"] is None


def test_a_real_position_angle_of_zero_degrees_is_not_mistaken_for_a_missing_one():
    """0 degrees is a real, common position angle - unlike separation or year, which never are 0 in practice. The
    row field must still be raw ("0"), so the template's own `is not none` check (not truthiness) is what decides it
    is present."""
    assert _component_fields("AB,3.9,0,2021")["POSITION_ANGLE"] == "0"


def test_a_missing_component_leaves_the_row_fields_none_rather_than_a_dash():
    """Un-rendered: the template adds its own missing-value fallback, so the row itself carries None rather than a
    pre-formatted "-"."""
    fields = _component_fields("")
    assert fields["SEPARATION"] is None
    assert fields["POSITION_ANGLE"] is None
    assert fields["YEAR"] is None


def test_a_group_members_magnitude_and_size_are_raw_values_not_html():
    """The template renders them itself, with the hand-ported PHP mirror of site/text.py's formatting."""
    member = Object(record={ObjectAttribute.NAME: "Member", ObjectAttribute.MAGNITUDE: "v9.22;v11.53",
                            ObjectAttribute.SIZE: "5.0x3.2"}, names=("Member",), groups=(), types=(), constellation="")
    row = _group_member(member, "en")
    assert row["GROUP_MEMBER_MAGNITUDE"] == "v9.22;v11.53"
    assert row["GROUP_MEMBER_SIZE"] == "5.0x3.2"
