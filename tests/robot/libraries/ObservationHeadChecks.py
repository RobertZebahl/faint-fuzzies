# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from faint_fuzzies.domain.observation import FoundObservation, Observation, VisibilityEntry, parse_optic
from faint_fuzzies.site.objects import SiteData, _description
from faint_fuzzies.site.projects import _deep_sky_observation, _optic_text


def head_items(optic, record=None, magnification=None, filter_=None):
    """The HEAD items an observation's instrument/conditions line shows (see site/objects.py's _description):
    `optic` is an OPTIC value ("A", "B,10x50", "R,70,400", ...), `record` its extra fields (BORTLE, NELM, SQM,
    SQML, SEEING), `magnification`/`filter_` a telescope visibility entry's own fields."""
    visibility = (VisibilityEntry(magnification, None, filter_),) if (magnification or filter_) else ()
    observation = Observation(record or {}, public=False, optic=parse_optic(optic), visibility=visibility)
    model = _description(observation, None, 1, "en", SiteData(), [])
    return model["HEAD"]


def optic_text(optic=None):
    """{"TEXT": ..., "KEY": ...} for an observation's OPTIC on a project page (see site/projects.py's
    _optic_text) - exactly one is given, both None when there is no optic."""
    observation = Observation({}, public=False, optic=parse_optic(optic) if optic else None, visibility=())
    text, key = _optic_text(observation)
    return {"TEXT": text, "KEY": key}


def deep_sky_conditions(record):
    """The CONDITIONS items a Deep Sky With Binoculars observation row shows (see site/projects.py's
    _deep_sky_observation) - the record's BORTLE/SQM/SQML/NELM, in that order."""
    observation = Observation(record, public=False, optic=parse_optic("A"), visibility=())
    found = FoundObservation(observation, None)
    row = _deep_sky_observation(found, "en", SiteData())
    return row["CONDITIONS"]
