"""The app's Site page builds from the data AppState already loaded (ui/state.py, README "The app's Site page"), not
from a fresh load, and can prune a file whose Object is gone. Fixture "site_datadir", in a copy (the build writes
into it), with the images its objects and DSS thumbnails need."""
import json
import shutil
from datetime import date

import pytest
from PIL import Image

from faint_fuzzies.loading import load_data_dir, load_static_catalogues
from faint_fuzzies.site.build import GlobalPages
from faint_fuzzies.ui.state import AppState
from tests.unit.builders import FIXTURES

DSS_FILE = "dss1_165241.40_+362735.00_20.jpg"
MELOTTE_ONLY = [{"NAME": "Melotte 20", "TYPE": "OC", "CONSTELLATION": "Per", "COORDINATES": "032700.00,+485000.00",
                 "PUBLISH_WITHOUT_OBSERVATION": True,
                 "OBSERVATIONS": [{"DESCRIPTION_DE": "Kopf", "DESCRIPTION_EN": "Header", "IMAGE": "header.jpg"}]}]


def _make_image(path, size=300):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (size, size), (90, 90, 120)).save(path, format="JPEG")


@pytest.fixture
def data(tmp_path):
    root = tmp_path / "data"
    shutil.copytree(FIXTURES / "site_datadir", root)
    _make_image(root / "observations" / "owner" / "sketches" / "m13.jpg")
    _make_image(root / "observations" / "owner" / "images" / "header.jpg")
    _make_image(root / "dss" / "objects" / DSS_FILE, 400)
    _make_image(root / "dss" / "objects" / "dss1_032700.00_+485000.00_5.jpg", 400)
    return root


def _build(data, out, **kwargs):
    """A build through AppState; no DSS image is fetched and no orbit drawn."""
    return AppState(data, fetch_dss=False, generate_orbits=False).build_site(out, **kwargs)


def test_a_globalpages_built_from_already_loaded_data_renders_the_same_as_a_fresh_load(data):
    static = load_static_catalogues(data)
    reused = GlobalPages(data, static=static, data=load_data_dir(data, static), optic_names={},
                         last_update=date(2026, 9, 16))
    fresh = GlobalPages(data, last_update=date(2026, 9, 16))
    assert reused.render_home("en") == fresh.render_home("en")


def test_appstate_build_site_writes_the_site_and_symlinks_its_images(data, tmp_path):
    out = tmp_path / "out"
    progress = []
    report = _build(data, out, on_progress=lambda step, fraction: progress.append((step, fraction)))
    assert report["pages"] == 80
    assert progress
    assert (out / "images" / "dss" / DSS_FILE).is_symlink()
    assert (out / "en" / "home.php").is_file()


def test_a_second_build_prunes_a_thumbnail_whose_object_is_gone(data, tmp_path):
    """The second build is a fresh AppState, since the first one keeps the old catalogue in memory. Pruning is
    opt-in (the Site page's "Prune" checkbox, off by default, like build-site's --prune)."""
    out = tmp_path / "out"
    _build(data, out)
    thumbnail = out / "images" / "dss" / "dss1_165241.40_+362735.00_20_web.jpg"
    assert thumbnail.is_file()
    (data / "observations" / "owner" / "objects.json").write_text(json.dumps(MELOTTE_ONLY), encoding="utf-8")
    report = _build(data, out, prune=True)
    assert not thumbnail.exists()
    assert report["pruned"] >= 1
    assert "Messier 13" not in (out / "en" / "observations-complete-object-list.php").read_text(encoding="utf-8")
