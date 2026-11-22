"""A double star Group's display name on the website: the WDS id is a name of the Group like any other, so when it is
the only one left after stripping, it must still be shown - not treated as an absent name (see CONTEXT.md's "WDS
id")."""
from types import SimpleNamespace

from faint_fuzzies.domain.model import ObjectAttribute
from faint_fuzzies.site.objects import get_display_names
from faint_fuzzies.site.projects import _names


def test_the_bare_wds_id_is_shown_when_it_is_the_groups_only_name():
    """A Group's own GROUP value can be just its WDS id, with no name common to every pair (see converters/wds.py's
    _group_name). That is still a real name, not an absence of one."""
    assert get_display_names("WDS01234+5678", None) == ["WDS01234+5678"]


def test_the_wds_id_is_still_dropped_when_another_name_is_also_common():
    assert get_display_names("beta 1 Cyg, WDS19307+2758", None) == ["beta 1 Cyg"]


def test_a_group_named_only_by_its_wds_id_is_not_renamed_after_its_pairs():
    """site/projects.py's double star entries used to fall back to unioning every member pair's own names whenever
    the Group's own name came up empty - showing names that are not common to the Group at all. The Group's own bare
    WDS id must be shown instead."""
    unit = SimpleNamespace(is_group=True, record={ObjectAttribute.GROUP: "WDS01234+5678"})
    assert _names(SimpleNamespace(unit=unit), None) == ["WDS01234+5678"]


def test_a_sketched_group_named_only_by_its_wds_id_keeps_that_name_in_the_gallery():
    """The gallery used to drop a trailing WDS id even when it was the only name, leaving a card titled
    "(**, Lyr)" for a sketch of a whole system such as STF2349's."""
    from faint_fuzzies.domain.model import ObjectType as T
    from faint_fuzzies.site.gallery import _title_and_link

    unit = SimpleNamespace(record={ObjectAttribute.GROUP: "WDS18366+3328"}, names=["WDS18366+3328"],
                           types=[T.DOUBLE_STAR], constellation="Lyr")
    assert _title_and_link(unit, "en")["OBJECT_LINK_NAME"] == "WDS18366+3328 (**, Lyr)"
