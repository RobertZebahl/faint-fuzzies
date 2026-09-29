# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from faint_fuzzies.domain.observation import Color, Difficulty, Grade, Observation, Optic, OpticType, VisibilityEntry
from faint_fuzzies.site.objects import SiteData, _description


def _result(spec):
    if spec in Difficulty.__members__:
        return Difficulty[spec]
    if spec in Color.__members__:
        return Color[spec]
    low_text, _, high_text = spec.partition("-")
    low = float(low_text)
    return Grade(low, float(high_text) if high_text else low)


def grade_badge(result_spec, public=False):
    """The GRADE (color), GRADE_TEXT and GRADE_KEY an observation's visibility result shows on the website
    (see site/objects.py's _description): `result_spec` is a Difficulty or Color member name, or a Grade
    as "low" or "low-high". A numeric Grade shows as GRADE_TEXT directly; a Difficulty/Color gives
    GRADE_KEY instead, since its word is content, looked up by grade_label (see
    site/static/php/description.php), not tested here."""
    optic = Optic("A", OpticType.NAKED_EYE)
    entry = VisibilityEntry(None, _result(result_spec), None)
    observation = Observation({}, public=public, optic=optic, visibility=(entry,))
    model = _description(observation, None, 1, "en", SiteData(), [])
    return {"GRADE": model["GRADE"], "GRADE_TEXT": model["GRADE_TEXT"], "GRADE_KEY": model["GRADE_KEY"]}
