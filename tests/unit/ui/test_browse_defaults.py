"""BrowsePage's default Catalogue and Observer filter selections (ui/browse.py: _default_catalogues,
_default_observers). Without the WDS catalogue selected by default too, the Objects table would never show a double
star at all; without the Observer also defaulting to the owner, it would default to showing the WDS's own ~170k
objects instead."""
from faint_fuzzies.domain.observer import Observers
from faint_fuzzies.ui.browse import _default_catalogues, _default_observers
from tests.unit.builders import OWNER, fake_collection

OWNER_OPTIONS = {"owner-example": "Owner Example (owner-example)"}


def _observers():
    return Observers("observers.json", [OWNER], [])


def test_nothing_is_narrowed_with_only_the_own_catalogue_loaded():
    assert _default_catalogues(fake_collection(["objects.json"])) == []


def test_the_own_catalogue_and_the_wds_are_both_selected_by_default():
    assert _default_catalogues(fake_collection(["objects.json", "wds.json"])) == ["objects.json", "wds.json"]


def test_a_catalogue_that_is_not_the_wds_is_not_added():
    assert _default_catalogues(fake_collection(["objects.json", "ugc.json"])) == ["objects.json"]


def test_the_owner_is_selected_by_default_alongside_the_wds():
    collection = fake_collection(["objects.json", "wds.json"])
    assert _default_observers(collection, _observers(), OWNER_OPTIONS) == ["owner-example"]


def test_the_owner_is_not_defaulted_with_only_one_catalogue_loaded():
    """Nothing to narrow, the same guard the Catalogue default uses."""
    collection = fake_collection(["objects.json"])
    assert _default_observers(collection, _observers(), OWNER_OPTIONS) == []


def test_the_owner_is_not_defaulted_when_not_among_the_dropdowns_own_options():
    """The owner has no observation anywhere, so the Observer dropdown never offers them - defaulting to their id
    anyway would select an option that is not actually there."""
    collection = fake_collection(["objects.json", "wds.json"])
    assert _default_observers(collection, _observers(), {}) == []


def test_the_owner_is_not_defaulted_without_an_observers_file():
    """No observers.json at all: falls back to the OWN_ID placeholder, which is never among the dropdown's own
    options either, so there is still nothing to default to."""
    collection = fake_collection(["objects.json", "wds.json"])
    assert _default_observers(collection, None, {}) == []
