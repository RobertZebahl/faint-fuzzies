# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""Direct, network-free checks of DSS fetch ordering (faint_fuzzies.media_pool._dss_run) and the live app's
lazy, shared thumbnail (faint_fuzzies.ui.media._thumbnail_url); both are stubbed or given only local files,
so nothing here ever reaches the network."""
import tempfile
from pathlib import Path

from PIL import Image

from faint_fuzzies.domain import dss
from faint_fuzzies.media_pool import _dss_run
from faint_fuzzies.ui.media import _thumbnail_url

_SOURCES = (dss.DSSSource.DSS1, dss.DSSSource.DSS2_RED)


def dss_fetch_calls(by_name, succeed_at=None):
    """Runs one DSSTask (two sources, DSS1 then DSS2_RED) through _dss_run with fetch_dss_image_by_name and
    fetch_dss_image_by_coordinates stubbed to record every attempt as ("name"/"coordinates", source value)
    and to succeed only for `succeed_at` (such a pair, or None to always fail); returns {"calls": the
    attempts made, in order, "succeeded": whether _dss_run reported success}."""
    calls = []

    def stub(kind):
        def run(_target, source, _fov, _destination):
            attempt = (kind, source.value)
            calls.append(attempt)
            return attempt == succeed_at
        return run

    original = dss.fetch_dss_image_by_name, dss.fetch_dss_image_by_coordinates
    dss.fetch_dss_image_by_name = stub("name")
    dss.fetch_dss_image_by_coordinates = stub("coordinates")
    try:
        task = dss.DSSTask(catalogue="own", label="M13", by_name=by_name, coordinates=(1.0, 2.0),
                           position="x", sources=_SOURCES, fov=5.0)
        succeeded = _dss_run(task, Path(tempfile.mkdtemp()))()
    finally:
        dss.fetch_dss_image_by_name, dss.fetch_dss_image_by_coordinates = original
    return {"calls": calls, "succeeded": succeeded}


def thumbnail_url_for_cached_image(valid_image):
    """Writes a cached "full-size" DSS image under a fresh data directory's dss/objects/ - a real one-pixel
    JPEG when `valid_image`, unreadable-as-an-image bytes otherwise - and returns {"url": _thumbnail_url's
    result, "thumbnail_written": whether a thumbnail file now exists next to it}. Covers both halves of
    get_dss_status's thumbnail handling without needing an AppState or an Object: made (and its URL
    returned) when the source is readable, None (so the caller falls back to the full-size image's own URL)
    when it is not."""
    data_dir = Path(tempfile.mkdtemp())
    path = data_dir / "dss" / "objects" / "dss1_010000.00_+200000.00_5.jpg"
    path.parent.mkdir(parents=True)
    if valid_image:
        Image.new("L", (300, 300)).save(path, format="JPEG")
    else:
        path.write_bytes(b"not an image")
    url = _thumbnail_url(data_dir, path)
    thumbnail = dss.thumbnail_path(path)
    return {"url": url, "thumbnail_written": thumbnail.is_file()}
