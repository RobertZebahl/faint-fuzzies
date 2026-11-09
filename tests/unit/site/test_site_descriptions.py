"""The text of an observation on the website: an observation a group took over from one of its pairs is led by the
pair (build_description_text). The local conditions near the object are a separate, structured list the template
itself leads with a label and joins (local_conditions_items) - its content (the "NELM"/"FST" word, the "Local
conditions near the object" label) is content, not tested here."""
from faint_fuzzies.site.objects import build_description_text, local_conditions_items


def test_the_description_is_just_the_given_text():
    assert build_description_text({"DESCRIPTION_EN": "Seen well"}, "en", None) == "Seen well"


def test_a_pairs_observation_is_led_by_the_pair():
    assert build_description_text({"DESCRIPTION_DE": "Gut zu sehen"}, "de", "STF919 (AB)") == "STF919 (AB): Gut zu sehen"


def test_no_local_conditions_give_no_items():
    assert local_conditions_items({}) == []


def test_sqm_l_and_seeing_give_plain_text_items():
    assert local_conditions_items({"SQML_LOCAL": "20.8", "SEEING_LOCAL": "3"}) == [
        {"TEXT": "SQM-L 20.8"}, {"TEXT": "Seeing 3"}]


def test_nelm_gives_a_key_item_its_value_with_a_plain_m():
    """Unlike the HEAD line's own NELM, which uses the styled superscript "m" (HTML_MAGNITUDE) - this one is embedded
    in already-escaped free text, so it stays a plain letter."""
    assert local_conditions_items({"NELM_LOCAL": "6.2"}) == [{"KEY": "nelm", "TEXT": " 6m2"}]
