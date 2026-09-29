# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""BrowsePage's default Catalogue and Observer filter selections (ui/browse.py: _default_catalogues,
_default_observers), without a browser or a data directory: a double star's own observations live on
its WDS pair/Group, not on an own-catalogue Object of its own - without the WDS catalogue selected by
default too, the Browse page's Objects table would never show a double star at all; without the
Observer also defaulting to the owner, it would default to the WDS's own ~170k objects instead."""
from faint_fuzzies.domain.observer import Observer, Observers, Scope
from faint_fuzzies.ui.browse import _default_catalogues, _default_observers

_OWNER = Observer(id="owner-example", firstname="Owner", surname="Example", scope=Scope.OWNER)
_OWNER_OPTIONS = {"owner-example": "Owner Example (owner-example)"}


class _FakeCatalogue:
    def __init__(self, name):
        self.name = name


class _FakeCollection:
    def __init__(self, *catalogue_names):
        self.catalogues = [_FakeCatalogue(name) for name in catalogue_names]


def default_catalogues_with_only_the_own_catalogue():
    """Nothing to narrow with only one catalogue loaded."""
    return _default_catalogues(_FakeCollection("objects.json"))


def default_catalogues_with_the_wds():
    return _default_catalogues(_FakeCollection("objects.json", "wds.json"))


def default_catalogues_without_the_wds():
    """A UGC or GCVS catalogue alongside the own one is not added - only the WDS is special-cased."""
    return _default_catalogues(_FakeCollection("objects.json", "ugc.json"))


def default_observers_with_the_wds_and_the_owner_option():
    collection = _FakeCollection("objects.json", "wds.json")
    observers = Observers("observers.json", [_OWNER], [])
    return _default_observers(collection, observers, _OWNER_OPTIONS)


def default_observers_with_a_single_catalogue():
    """Nothing to narrow with only one catalogue loaded - the same guard _default_catalogues uses."""
    collection = _FakeCollection("objects.json")
    observers = Observers("observers.json", [_OWNER], [])
    return _default_observers(collection, observers, _OWNER_OPTIONS)


def default_observers_without_an_owner_option():
    """The owner has no observation anywhere, so _observer_options never offered them - nothing to
    default to, rather than selecting an id the dropdown does not actually show."""
    collection = _FakeCollection("objects.json", "wds.json")
    observers = Observers("observers.json", [_OWNER], [])
    return _default_observers(collection, observers, {})


def default_observers_without_an_observers_file():
    """No observers.json at all: falls back to the OWN_ID placeholder, which is never among the
    dropdown's own options either, so there is still nothing to default to."""
    collection = _FakeCollection("objects.json", "wds.json")
    return _default_observers(collection, None, {})
