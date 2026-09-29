# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.site.output import _broken_page_links, _scan_links


def broken_links(output_dir, page_hrefs, page_anchors):
    """`_broken_page_links`, for a hand-built `output_dir` and hand-built page_hrefs/page_anchors dicts
    ({relative path: [href, ...]} / {relative path: [anchor, ...]})."""
    anchors = {relative: set(values) for relative, values in page_anchors.items()}
    return _broken_page_links(Path(output_dir), page_hrefs, anchors)


def scanned_hrefs(document):
    """The `<a href>` targets `_scan_links` finds in `document`, in order."""
    return _scan_links(document).hrefs


def scanned_anchors(document):
    """The `id`/`name` anchors `_scan_links` finds in `document`, as a sorted list."""
    return sorted(_scan_links(document).anchors)
