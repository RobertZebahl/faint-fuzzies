"""The HEAD items an observation's instrument/conditions line shows (site/objects.py's _description), a project
page's own OPTIC text/key (site/projects.py's _optic_text) and a Deep Sky With Binoculars observation's CONDITIONS
items (site/projects.py's _deep_sky_observation) - structural only; the word a KEY resolves to is content, looked up
by head_label (see site/static/php/description.php), not tested here."""
from faint_fuzzies.domain.observation import FoundObservation, Observation, VisibilityEntry, parse_optic
from faint_fuzzies.site.objects import SiteData, _description
from faint_fuzzies.site.projects import _deep_sky_observation, _optic_text

NAKED_EYE = {"KEY": "naked-eye", "TEXT": ""}


def _head(optic, record=None, magnification=None, filter_=None):
    visibility = (VisibilityEntry(magnification, None, filter_),) if (magnification or filter_) else ()
    observation = Observation(record or {}, public=False, optic=parse_optic(optic), visibility=visibility)
    return _description(observation, None, 1, "en", SiteData(), [])["HEAD"]


def _optic_text_and_key(optic=None):
    return _optic_text(Observation({}, public=False, optic=parse_optic(optic) if optic else None, visibility=()))


def test_the_naked_eye_gives_a_key_item_with_no_suffix():
    assert _head("A") == [NAKED_EYE]


def test_an_instrument_falls_back_to_its_own_code_without_a_readable_name():
    assert _head("R,70,400") == [{"TEXT": "R,70,400"}]


def test_bortle_is_a_plain_text_item():
    assert _head("A", {"BORTLE": "6-"}) == [NAKED_EYE, {"TEXT": "Bortle 6-"}]


def test_sqm_sqm_l_and_seeing_are_plain_text_items_in_that_order():
    assert _head("A", {"SQM": "21.0", "SQML": "19.5", "SEEING": "3/5"}) == [
        NAKED_EYE, {"TEXT": "SQM 21.0"}, {"TEXT": "SQM-L 19.5"}, {"TEXT": "Seeing 3/5"}]


def test_nelm_is_a_key_item_its_value_with_the_styled_superscript_m():
    """Unlike local_conditions_items' own NELM (see test_site_descriptions.py), which is embedded in already-escaped
    free text and so uses a plain letter instead."""
    items = _head("A", {"NELM": "5.4"})
    assert len(items) == 2
    assert items[1]["KEY"] == "nelm"
    assert "<sup>m</sup>" in items[1]["TEXT"]
    assert "5" in items[1]["TEXT"]
    assert "4" in items[1]["TEXT"]


def test_magnification_and_a_filter_are_one_plain_text_item():
    assert _head("R,70,400", magnification=100, filter_="OIII") == [{"TEXT": "R,70,400"}, {"TEXT": "100x + [OIII]"}]


def test_a_project_page_shows_binoculars_as_magnification_by_aperture():
    assert _optic_text_and_key("B,10x50") == ("10x50", None)


def test_a_project_page_shows_the_naked_eye_by_its_content_key():
    assert _optic_text_and_key("A") == (None, "naked-eye")


def test_a_project_page_shows_a_telescope_by_its_aperture():
    assert _optic_text_and_key("R,70,400") == ("70mm", None)


def test_a_project_page_shows_nothing_for_no_optic():
    assert _optic_text_and_key() == (None, None)


def test_a_deep_sky_observations_conditions_are_bortle_sqm_l_then_nelm():
    observation = Observation({"BORTLE": "4", "SQML": "20.1", "NELM": "6.2"}, public=False, optic=parse_optic("A"),
                              visibility=())
    items = _deep_sky_observation(FoundObservation(observation, None), "en", SiteData())["CONDITIONS"]
    assert len(items) == 3
    assert items[0] == {"TEXT": "Bortle 4"}
    assert items[1] == {"TEXT": "SQM-L 20.1"}
    assert items[2]["KEY"] == "nelm"
    assert "<sup>m</sup>" in items[2]["TEXT"]
