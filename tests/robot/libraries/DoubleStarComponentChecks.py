# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""A double star pair's component fields on the website (site/objects.py: get_pair_component,
_double_star_components) and a (non-double star) group member's magnitude/size (_group_member) - all raw,
un-rendered values, for the template to format itself (see README.md's "Formatting raw values")."""
from faint_fuzzies.domain.model import Object, ObjectAttribute
from faint_fuzzies.site.objects import SiteData, _double_star_components, _group_member, get_pair_component

_SITE = SiteData()


def _pair(component=""):
    return Object(record={ObjectAttribute.COMPONENT: component}, names=("Pair",), groups=(), types=(),
                 constellation="")


def pair_component(component):
    """name/separation/angle/year of a pair's own COMPONENT, each None when missing (see get_pair_component)."""
    return get_pair_component(_pair(component), _SITE)


def double_star_component_fields(component):
    """The one entry _double_star_components builds for a single pair with this COMPONENT: its raw
    SEPARATION, POSITION_ANGLE and YEAR, exactly as the template receives them."""
    row = {}
    _double_star_components(row, [_pair(component)], "en", _SITE, True)
    entry = row["DOUBLESTAR_COMPONENTS"][0]
    return {"SEPARATION": entry["SEPARATION"], "POSITION_ANGLE": entry["POSITION_ANGLE"], "YEAR": entry["YEAR"]}


def group_member_magnitude_and_size(magnitude="", size=""):
    """A group member's GROUP_MEMBER_MAGNITUDE/GROUP_MEMBER_SIZE: raw values, not HTML (see _group_member)."""
    member = Object(record={ObjectAttribute.NAME: "Member", ObjectAttribute.MAGNITUDE: magnitude,
                            ObjectAttribute.SIZE: size}, names=("Member",), groups=(), types=(), constellation="")
    row = _group_member(member, "en")
    return (row["GROUP_MEMBER_MAGNITUDE"], row["GROUP_MEMBER_SIZE"])
