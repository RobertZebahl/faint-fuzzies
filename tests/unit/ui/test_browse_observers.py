"""The Observer filter dropdown of the Browse page (ui/browse.py: _observer_options). An own-catalogue observation
never carries an Observer even though it is the owner's, so the registered OWNER-scope observer would otherwise
vanish from the dropdown as soon as the owner stops also having a community-imported observation (such as a project
CSV submission)."""
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.ui.browse import _observer_options
from tests.unit.builders import OWNER, fake_collection


def _object(observations=(), community_observations=()):
    return Object(record={}, names=(), groups=(), types=(), constellation="",
                  observations=observations, community_observations=list(community_observations))


def _observation(observer=None):
    return Observation({}, public=True, optic=None, visibility=(), observer=observer)


def _observer_ids(objects, observers):
    return list(_observer_options(fake_collection(objects=objects), observers).keys())


def test_the_owner_appears_from_an_own_observation_alone():
    """Regression case: the owner removed their project-double-stars submission folder, keeping only their
    own-catalogue observations (now that photographs can be attached there directly) - they must still be offered
    in the Observer filter."""
    ids = _observer_ids([_object(observations=(_observation(),))], Observers("observers.json", [OWNER], []))
    assert "owner-example" in ids


def test_the_owner_is_left_out_with_no_observation_at_all():
    ids = _observer_ids([_object()], Observers("observers.json", [OWNER], []))
    assert "owner-example" not in ids


def test_a_community_imported_observation_still_works_without_an_observers_file():
    ids = _observer_ids([_object(community_observations=(_observation(OWNER),))], None)
    assert "owner-example" in ids
