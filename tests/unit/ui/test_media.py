"""The live app's lazy, shared DSS thumbnail (ui/media.py: _thumbnail_url, used by get_dss_status), and its fallback
to the full-size image's own URL when making it fails."""
from PIL import Image

from faint_fuzzies.domain import dss
from faint_fuzzies.ui.media import _thumbnail_url


def _cached_image(data_dir):
    path = data_dir / "dss" / "objects" / "dss1_010000.00_+200000.00_5.jpg"
    path.parent.mkdir(parents=True)
    return path


def test_a_readable_cached_image_gets_a_shared_thumbnail(tmp_path):
    """The app makes the same shared, 200x200 thumbnail the website builder would, next to the full-size image."""
    path = _cached_image(tmp_path)
    Image.new("L", (300, 300)).save(path, format="JPEG")
    assert _thumbnail_url(tmp_path, path) == "/media/dss/objects/dss1_010000.00_+200000.00_5_web.jpg"
    assert dss.thumbnail_path(path).is_file()


def test_when_making_the_thumbnail_fails_the_full_size_images_own_url_is_used_instead(tmp_path):
    """Only the half _thumbnail_url is responsible for: it returns None, and get_dss_status falls back."""
    path = _cached_image(tmp_path)
    path.write_bytes(b"not an image")
    assert _thumbnail_url(tmp_path, path) is None
    assert not dss.thumbnail_path(path).is_file()
