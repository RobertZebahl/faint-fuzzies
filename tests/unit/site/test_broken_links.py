"""The build's broken-link check (site/output.py's `_broken_page_links`/`_scan_links`): every page's `<a href>` is
checked against the pages and anchors actually on disk, whether rendered this run (`page_hrefs`/`page_anchors`,
passed in directly) or only seeded by `base`/the static folder (read from disk instead)."""
from faint_fuzzies.site.output import _broken_page_links, _scan_links


def _broken(output_dir, page_hrefs, page_anchors):
    anchors = {relative: set(values) for relative, values in page_anchors.items()}
    return _broken_page_links(output_dir, page_hrefs, anchors)


def _page(output_dir, relative, text):
    path = output_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_link_to_a_missing_page_is_reported(tmp_path):
    broken = _broken(tmp_path, {"en/home.php": ["missing.php"]}, {"en/home.php": []})
    assert len(broken) == 1
    assert "missing.php" in broken[0]


def test_a_link_to_an_existing_page_with_a_matching_anchor_is_not_reported(tmp_path):
    """The anchors of "target.php", which is not in page_anchors at all, are read from disk."""
    _page(tmp_path, "en/target.php", '<a id="Foo" class="anchor"></a>')
    assert not _broken(tmp_path, {"en/home.php": ["target.php#Foo"]}, {"en/home.php": []})


def test_a_link_to_an_existing_page_with_a_missing_anchor_is_reported(tmp_path):
    _page(tmp_path, "en/target.php", '<a id="Foo" class="anchor"></a>')
    broken = _broken(tmp_path, {"en/home.php": ["target.php#Bar"]}, {"en/home.php": []})
    assert len(broken) == 1
    assert "Bar" in broken[0]


def test_a_same_page_anchor_is_checked_against_the_pages_own_anchors(tmp_path):
    _page(tmp_path, "en/home.php", "anything")
    assert not _broken(tmp_path, {"en/home.php": ["#Foo"]}, {"en/home.php": ["Foo"]})
    assert len(_broken(tmp_path, {"en/home.php": ["#Foo"]}, {"en/home.php": []})) == 1


def test_an_external_href_is_never_checked(tmp_path):
    """No files exist for any of these, and none is reported - there is no network access here."""
    hrefs = ["http://example.com/missing", "mailto:x@y.com", "//cdn.example.com/x"]
    assert not _broken(tmp_path, {"en/home.php": hrefs}, {"en/home.php": []})


def test_a_query_string_is_stripped_before_resolving_the_page(tmp_path):
    _page(tmp_path, "en/home.php", "anything")
    assert not _broken(tmp_path, {"en/home.php": ["?list=foo"]}, {"en/home.php": []})


def test_an_empty_href_or_a_bare_hash_is_ignored(tmp_path):
    """A bare "#" is a same-page link without an anchor, so it is only fine while the page itself is on disk - as it
    always is in a real build, where it has just been written."""
    _page(tmp_path, "en/home.php", "anything")
    assert not _broken(tmp_path, {"en/home.php": ["", "#"]}, {"en/home.php": []})


def test_a_relative_path_cannot_escape_the_output_folder(tmp_path):
    assert len(_broken(tmp_path, {"en/home.php": ["../../../../etc/evil.php"]}, {"en/home.php": []})) == 1


def test_a_media_reference_is_left_to_the_existing_missing_image_check(tmp_path):
    """The image "../images/dss/x.jpg" is not a page link - it is the existing check's job, and it must never be reported
    here even though no such file exists."""
    assert not _broken(tmp_path, {"en/home.php": ["../images/dss/x.jpg"]}, {"en/home.php": []})


def test_a_percent_encoded_path_is_decoded_before_resolving_the_page(tmp_path):
    _page(tmp_path, "en/target+page.php", "anything")
    assert not _broken(tmp_path, {"en/home.php": ["target%2Bpage.php"]}, {"en/home.php": []})


def test_a_php_string_concatenation_is_not_mistaken_for_a_page(tmp_path):
    """A language switcher built as `'<a href="'.$url.'">'` leaves a literal `'.$url.'` as the href text once
    HTMLParser reads the quotes - a runtime PHP value no build-time scan can resolve."""
    assert not _broken(tmp_path, {"en/home.php": ["'.$url.'"]}, {"en/home.php": []})


def test_a_link_inside_a_php_echo_is_still_found():
    """Jinja has already resolved every {{ }} placeholder before this text is ever written, so the href is plain
    text by the time this runs, whichever side of the PHP "if" it is on."""
    document = """<?php if ($list) {
echo '<a href="project-double-stars.php?list=foo#STF999">x</a>';
} else {
echo '<a href="project-double-stars.php#STF999">x</a>';
} ?>"""
    assert _scan_links(document).hrefs == ["project-double-stars.php?list=foo#STF999", "project-double-stars.php#STF999"]


def test_both_id_and_name_anchors_are_recognised():
    document = '<a id="Foo" class="anchor"></a><a name="Bar" class="anchor"></a>'
    assert sorted(_scan_links(document).anchors) == ["Bar", "Foo"]
