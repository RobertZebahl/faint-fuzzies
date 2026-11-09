"""The GRADE/GRADE_TEXT/GRADE_KEY badge an observation's visibility result shows on the website (site/objects.py's
_description): Grade is private observations only, Difficulty and Colour are public observations only (see
CONTEXT.md's Conditions and domain/observation.py's _check_visibility_results, which rejects any other pairing). A
Difficulty/Colour's word is content (see grade_label in site/static/php/description.php), so only its GRADE_KEY is
checked here, not the word itself."""
from faint_fuzzies.domain.observation import Color, Difficulty, Grade, Observation, Optic, OpticType, VisibilityEntry
from faint_fuzzies.site.objects import SiteData, _description


def _badge(result, public):
    entry = VisibilityEntry(None, result, None)
    observation = Observation({}, public=public, optic=Optic("A", OpticType.NAKED_EYE), visibility=(entry,))
    return _description(observation, None, 1, "en", SiteData(), [])


def test_a_numeric_grade_range_shows_as_text_not_as_a_colored_badge():
    badge = _badge(Grade(3.0, 4.0), public=False)
    assert badge["GRADE_TEXT"] == "3-4"
    assert badge["GRADE"] == "#FFFFFF"


def test_a_single_value_grade_shows_just_the_one_number():
    assert _badge(Grade(5.0, 5.0), public=False)["GRADE_TEXT"] == "5"


def test_a_difficulty_result_shows_its_colored_badge():
    badge = _badge(Difficulty.EASY, public=True)
    assert badge["GRADE_KEY"] == "easy"
    assert badge["GRADE"] == "#24B92C"


def test_a_colour_result_shows_its_colored_badge():
    badge = _badge(Color.RED, public=True)
    assert badge["GRADE_KEY"] == "red"
    assert badge["GRADE"] == "#E61E11"
