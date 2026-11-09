"""Orbit diagrams (domain/orbits.py, media_pool.py): a pair can have several published solutions, all plottable ones
are kept - numbered in file order, only when more than one can be plotted - and a solution's file name only has
letters, digits and hyphens after the WDS id."""
from pathlib import Path

import pytest
from PIL import Image

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import component_of
from faint_fuzzies.domain.orbits import (
    OrbitalElements,
    _orbit_geometry,
    ephemeris_step,
    generate_orbit_diagram,
    parse_orbits,
)
from faint_fuzzies.media_pool import matched_orbits, orbit_cache_path, orbit_stem
from tests.unit.builders import FIXTURES, orbits_file_text

WDS = FIXTURES / "datadir" / "catalogues" / "wds.json"
STF999 = ("WDS11111+2222", "STF 999", "y")


@pytest.fixture(scope="module")
def wds():
    return Collection([load_catalogue(WDS)])


def _solutions_by_pair(collection, entries):
    """For each pair that got a plottable solution from `entries` (each a WDS id, designation and period unit):
    "label component" (for example "BU17 ac") -> [(file name, title, number)]."""
    elements = [OrbitalElements(wds_id=wds_id, designation=designation, period=100.0, period_unit=unit,
                                semi_major_axis=1.0, inclination=60.0, node=30.0, periastron=1950.0,
                                eccentricity=0.3, periastron_longitude=45.0, grade=3)
                for wds_id, designation, unit in entries]
    keys = {id(obj): f"{obj.label} {component_of(obj)}" for obj in collection.objects}
    return {keys[object_id]: [(orbit_cache_path(Path("data"), s).name, s.title, s.number) for s in solutions]
            for object_id, solutions in matched_orbits(collection, elements).items()}


def _elements(period, semi_major_axis, eccentricity, inclination, node, periastron, omega):
    return OrbitalElements(wds_id="WDS00000+0000", designation="X 1", period=period, period_unit="y",
                           semi_major_axis=semi_major_axis, inclination=inclination, node=node,
                           periastron=periastron, eccentricity=eccentricity, periastron_longitude=omega, grade=2)


def _diagram(tmp_path):
    """Draws the diagram of STF999 (errors filled in) for the year 2025; returns the written file."""
    (elements,) = parse_orbits(orbits_file_text([STF999], errors=True))
    destination = tmp_path / "orbit.jpg"
    assert generate_orbit_diagram(elements, "Test", destination, year=2025), "no diagram was written"
    return destination


def _table_rows(tmp_path, monkeypatch, *elements):
    """The rows of the table of positions a diagram draws for 2026 (year, separation, position angle as text)."""
    from matplotlib.axes import Axes
    seen = []
    real_table = Axes.table

    def spy(self, *args, **kwargs):
        seen.append(kwargs.get("cellText"))
        return real_table(self, *args, **kwargs)

    monkeypatch.setattr(Axes, "table", spy)
    generate_orbit_diagram(_elements(*elements), "Test", tmp_path / "orbit.jpg", year=2026)
    return [list(row) for row in seen[1][1:]]  # the second table is the one of positions; without its header


# period, axis, e, i, node, T, omega
FAST = (0.54643, 0.019, 0.302, 146.3, 51.2, 1990.675, 86.65)
QUARTERS = (3.1, 0.1, 0.3, 60.0, 30.0, 2020.0, 45.0)
HALVES = (8.4, 0.2, 0.3, 60.0, 30.0, 2020.0, 45.0)
YEARLY = (106.7, 1.44, 0.45, 45.0, 221.0, 1943.1, 277.0)
SLOW = (55000.0, 110.0, 0.87, 81.0, 170.0, -3500.0, 130.0)


@pytest.mark.parametrize("header_lines", [0, 1, 7, 12])
def test_the_number_of_header_lines_does_not_matter(header_lines):
    """A data line is recognised by its own shape (a fixed-width RA,Dec position at the start), not by a fixed count
    of lines before it - the source has been seen with seven header lines and with none at all."""
    entries = [STF999, ("WDS02333+1234", "BU 17AB", "y")]
    assert len(parse_orbits(orbits_file_text(entries, header_lines=header_lines))) == 2


def test_a_pair_with_one_solution_has_a_plain_name(wds):
    assert _solutions_by_pair(wds, [STF999])["STF999 ab"] == [("STF999-AB-orbit.jpg", "STF999 [AB]", None)]


def test_a_pair_with_several_solutions_keeps_each_of_them_in_file_order(wds):
    solutions = _solutions_by_pair(wds, [STF999, STF999, STF999])["STF999 ab"]
    assert len(solutions) == 3
    assert solutions[0] == ("STF999-AB-orbit-solution-1.jpg", "STF999 [AB] - Solution 1", 1)
    assert solutions[2] == ("STF999-AB-orbit-solution-3.jpg", "STF999 [AB] - Solution 3", 3)


def test_a_solution_that_cannot_be_plotted_is_not_counted(wds):
    """A period in days cannot be plotted, so the plottable one is the pair's only diagram and has a plain name, not
    "-solution-2"."""
    solutions = _solutions_by_pair(wds, [("WDS11111+2222", "STF 999", "d"), STF999])["STF999 ab"]
    assert solutions == [("STF999-AB-orbit.jpg", "STF999 [AB]", None)]


def test_solutions_of_different_pairs_of_one_group_stay_apart(wds):
    """BU17 has two pairs (AB and AC) under one WDS id; the designation's suffix tells them apart, so each pair has
    one solution and neither is numbered."""
    found = _solutions_by_pair(wds, [("WDS02333+1234", "BU 17AB", "y"), ("WDS02333+1234", "BU 17AC", "y")])
    assert len(found) == 2
    assert sorted(s[0][0] for s in found.values()) == ["BU17-AB-orbit.jpg", "BU17-AC-orbit.jpg"]


@pytest.mark.parametrize(("name", "component", "number", "stem"), [
    ("STF2382", "AB", 1, "STF2382-AB-orbit-solution-1"),
    ("CHR112", "Aa-Ab", None, "CHR112-Aa-Ab-orbit"),
    ("A1", "", None, "A1-orbit"),
    ("2 Sge", "AB", None, "2-Sge-AB-orbit"),
])
def test_file_names_match_existing_orbit_images(name, component, number, stem):
    """The pair's first name with hyphens for spaces, its component as written, and the number only when it has
    several solutions, so that an existing orbit image is reused."""
    assert orbit_stem(name, component, number) == stem


def test_file_names_only_hold_letters_digits_and_hyphens():
    """An asterisk is not allowed in a Windows file name."""
    assert orbit_stem("Sgr A*-S1", "", None) == "Sgr-A--S1-orbit"


def test_the_title_names_every_pair_name_and_the_component(wds):
    """All names except the WDS id, the component in brackets, the number only when the pair has several
    solutions."""
    assert _solutions_by_pair(wds, [("WDS19244+1656", "STFA 41AB", "y")])["STFA41 ab"][0][1] == "STFA41, 2 Sge [AB]"


def test_the_errors_and_the_unit_of_the_axis_are_kept():
    """The plot is the same in any unit and the errors are only shown, but the diagram writes both as the file gives
    them."""
    (elements,) = parse_orbits(orbits_file_text([STF999], errors=True))
    assert elements.semi_major_axis_unit == "m"
    assert elements.semi_major_axis == 1.0
    assert [elements.period_error, elements.semi_major_axis_error, elements.inclination_error, elements.node_error,
            elements.periastron_error, elements.eccentricity_error, elements.periastron_longitude_error] == [
        0.5, 0.02, 1.5, 2.0, 0.3, 0.01, 3.0]


def test_a_diagram_is_written_as_a_picture(tmp_path):
    width, height = Image.open(_diagram(tmp_path)).size
    assert width > 900
    assert height > 900


@pytest.mark.parametrize(("elements", "step"), [
    pytest.param(FAST, 0.05, id="under 10 years: about one revolution"),
    pytest.param(QUARTERS, 0.25, id="3.1 years"),
    pytest.param(HALVES, 0.5, id="8.4 years"),
    pytest.param(YEARLY, 1, id="otherwise a year"),
    pytest.param(SLOW, 20, id="unless the pair hardly moves in ten years"),
])
def test_the_table_steps_fit_the_period(elements, step):
    """Under 10 years: about one revolution in the table. Otherwise a year, unless the pair hardly moves in ten of
    them."""
    assert ephemeris_step(_elements(*elements), 2026.0) == pytest.approx(step)


def test_todays_position_is_drawn_in_red(tmp_path):
    pixels = Image.open(_diagram(tmp_path)).convert("RGB").getdata()
    assert sum(1 for r, g, b in pixels if r > 200 and g < 80 and b < 80) > 50


@pytest.mark.parametrize(("elements", "decimals"), [(FAST, 3), (YEARLY, 2)])
def test_small_separations_get_more_decimals(tmp_path, monkeypatch, elements, decimals):
    """Two decimals would show 0.02, 0.02, 0.01 for a pair with a separation of 0.015 arcseconds."""
    assert len(_table_rows(tmp_path, monkeypatch, *elements)[0][1].split(".")[1]) == decimals


@pytest.mark.parametrize(("elements", "row", "year"), [
    (QUARTERS, 1, "2026.25"),
    (QUARTERS, 3, "2026.75"),
    (HALVES, 1, "2026.5"),
    (YEARLY, 1, "2027.0"),
])
def test_the_years_of_the_table_are_written_exactly(tmp_path, monkeypatch, elements, row, year):
    """A step of a quarter year needs two decimals: 2026.25, not 2026.2."""
    assert _table_rows(tmp_path, monkeypatch, *elements)[row][0] == year


@pytest.mark.parametrize(("inclination", "count"), [(90.0, 3), (60.0, 5), (85.0, 5), (95.0, 5)])
def test_an_orbit_seen_edge_on_is_marked_in_quarters_not_sixths(inclination, count):
    """85 < inclination < 95 is edge-on: 3 labeled positions besides today's (quarters), not 5 (sixths). 85 and 95
    themselves are not edge-on."""
    geometry = _orbit_geometry(_elements(4.0, 0.1, 0.3, inclination, 30.0, 2020.0, 45.0), 2026)
    assert sum(1 for point in geometry.points if point[4] is not None) == count
