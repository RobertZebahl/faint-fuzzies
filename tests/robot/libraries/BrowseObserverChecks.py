# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""BrowsePage's Observer filter dropdown (ui/browse.py: _observer_options), without a browser or a data
directory: an own-catalogue observation never carries an Observer (Observation.observer is None even
though it is the owner's), so the registered OWNER-scope observer has to be added explicitly whenever
there is at least one own observation - not just when the owner also happens to have a community-imported
one, such as a project CSV submission (see the "owner removed their project folder" case this
was written for)."""
from faint_fuzzies.domain.model import Object
from faint_fuzzies.domain.observation import Observation
from faint_fuzzies.domain.observer import Observer, Observers, Scope
from faint_fuzzies.ui.browse import _observer_options

_OWNER = Observer(id="owner-example", firstname="Owner", surname="Example", scope=Scope.OWNER)


class _FakeCollection:
    def __init__(self, objects):
        self.objects = objects


def _object(observations=(), community_observations=()):
    return Object(record={}, names=(), groups=(), types=(), constellation="",
                 observations=observations, community_observations=list(community_observations))


def _own_observation():
    return Observation({}, public=True, optic=None, visibility=())


def _community_observation(observer):
    return Observation({}, public=True, optic=None, visibility=(), observer=observer)


def observer_ids_with_only_an_own_observation():
    """The owner is registered but has never submitted through a project CSV - only their own-catalogue
    observation exists. They must still appear in the dropdown."""
    collection = _FakeCollection([_object(observations=(_own_observation(),))])
    observers = Observers("observers.json", [_OWNER], [])
    return list(_observer_options(collection, observers).keys())


def observer_ids_with_no_observation_at_all():
    """The owner is registered but nothing anywhere is attributed to them yet - own or community - so
    they are left out, the same as any other observer with nothing to filter for."""
    collection = _FakeCollection([_object()])
    observers = Observers("observers.json", [_OWNER], [])
    return list(_observer_options(collection, observers).keys())


def observer_ids_with_a_community_observation_only():
    """Unaffected regression check: the pre-existing path (a community-imported observation, such as
    another observer's) still puts its observer in the dropdown even with no Observers file at all."""
    collection = _FakeCollection([_object(community_observations=(_community_observation(_OWNER),))])
    return list(_observer_options(collection, None).keys())
