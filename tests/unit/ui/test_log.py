"""The Log page (ui/log.py): all the Findings of a loaded data directory in one table (errors first, then by source
and row), each row linked to the Object it is about, with filters; and the background tasks that failed.

Fixture "info_link_datadir": a WDS pair INF1 and a second, INF2, each with a non-default component already set - a
community row naming INF1 with no component, and an own-catalogue attach-record naming INF2 with no component, each
match their pair but still get an info finding ("'X' is the pair AC"), to check that an info finding links to its
Object the same way a warning does. A third pair, INF3, has an own-catalogue attach-record naming it alongside a
second, non-matching name ("Nonexistent Designation"), to check that the resulting "does not match" warning links to
it too. A deep sky object, "INF Deep Sky", has a Global community row naming it alongside a second, non-matching name
("Nonexistent Deep Sky Object"), the same check for a deep sky Object.
"""
import datetime

import pytest

from faint_fuzzies.tasks import TaskFailure
from faint_fuzzies.ui.browse import find_object
from faint_fuzzies.ui.log import _FINDING_ROW_BODY, failure_rows, filter_rows, log_rows
from tests.unit.builders import FIXTURES, load_world


@pytest.fixture(scope="module")
def problems():
    return load_world(FIXTURES / "problems_datadir")


def _summary(world):
    """(level, source, row, observation, object, href) of every row, in the order of the page."""
    return [(r["level"], r["source"], r["row"], r["observation"], r["object"], r["href"])
            for r in log_rows(world.findings)]


@pytest.fixture(scope="module")
def info_link_rows():
    return _summary(load_world(FIXTURES / "info_link_datadir"))


def _row_about(rows, label):
    return next(r for r in rows if r[4] == label)


def test_every_finding_is_a_row_with_errors_first(problems):
    rows = _summary(problems)
    assert [r[0] for r in rows] == ["error"] * 7 + ["warning"]
    assert [r[4] for r in rows] == ["Unknown Type", "objects.json #3", "objects.json #4", "Half Bad", "Only Bad",
                                    "Missing Sketch", "Not Placed", "Warned"]


def test_a_row_names_its_source_record_and_observation(problems):
    assert _summary(problems)[3] == ("error", "objects.json", 5, 1, "Half Bad", "/?object=objects.json%3A5")


def test_a_row_about_an_object_links_to_it(problems):
    """Also an Invalid one, which is known by its place."""
    links = [r[5] for r in _summary(problems)]
    assert links[1] == "/?object=objects.json%3A3"
    assert "" not in links


@pytest.mark.parametrize(("reference", "label"), [
    ("objects.json:5", "Half Bad"),
    ("objects.json:3", "objects.json #3"),
    ("objects.json:99", None),
    ("nothing", None),
])
def test_the_link_finds_the_object_again(problems, reference, label):
    found = find_object(problems.collection, reference)
    assert (None if found is None else found.label) == label


@pytest.mark.parametrize(("levels", "sources", "text", "expected"), [
    (["warning"], [], "", ["Warned"]),
    ([], ["other.json"], "", []),
    ([], [], "SKETCH", ["Missing Sketch"]),
    (["error"], [], "optic", ["Half Bad", "Only Bad"]),
])
def test_the_rows_are_filtered_by_level_source_and_text(problems, levels, sources, text, expected):
    assert [r["object"] for r in filter_rows(log_rows(problems.findings), levels, sources, text)] == expected


def test_a_failed_task_is_a_row_with_its_time_and_what_it_was_for():
    when = datetime.datetime(2026, 9, 26, 12, 30, 5)  # noqa: DTZ001  # TaskFailure.time is naive (datetime.now)
    rows = failure_rows([TaskFailure("a.jpg", "dss", "M 13", "no image", when),
                         TaskFailure("b.jpg", "orbit", "", "boom", when)])
    assert [(r["time"], r["kind"], r["what"], r["message"]) for r in rows] == [
        ("12:30:05", "dss", "M 13", "no image"), ("12:30:05", "orbit", "b.jpg", "boom")]


def test_a_row_of_a_community_file_links_to_the_object_it_matched():
    """Fixture "component_datadir": a warning about a row that was attached (SYS1 is a group without the component
    of the row) is about the Object it went to; a row that matched nothing (TWIN8, an error) is about no Object, so it
    has no link."""
    rows = _summary(load_world(FIXTURES / "component_datadir"))
    assert rows[0] == ("error", "anna-example/visual.csv", 11, "", "TWIN8", "")
    assert rows[4] == ("warning", "anna-example/visual.csv", 4, "", "SYS1", "/?object=objects.json%3A1")


def test_an_info_finding_links_to_its_object_too_whether_from_a_community_row_or_an_own_catalogue_attach_record(
        info_link_rows):
    assert _row_about(info_link_rows, "INF1") == (
        "info", "anna-example/global.csv", 1, "", "INF1", "/?object=wds.json%3A1")
    assert _row_about(info_link_rows, "INF2") == ("info", "objects.json", 1, "", "INF2", "/?object=wds.json%3A2")


def test_a_non_matching_name_alongside_a_matching_one_also_links_to_the_matched_object(info_link_rows):
    assert _row_about(info_link_rows, "INF3") == ("warning", "objects.json", 2, "", "INF3", "/?object=wds.json%3A3")


def test_the_same_rule_links_a_deep_sky_community_rows_non_matching_name_too(info_link_rows):
    """The message's "object" wording, rather than "double star", is checked in community.robot, where the
    message text is available."""
    row = _row_about(info_link_rows, "INF Deep Sky")
    assert row[0] == "warning"
    assert row[5] == "/?object=objects.json%3A3"


def test_an_object_link_opens_in_a_new_tab():
    """Like the Group link of the detail panel."""
    assert ':href="props.row.href" target="_blank"' in _FINDING_ROW_BODY
