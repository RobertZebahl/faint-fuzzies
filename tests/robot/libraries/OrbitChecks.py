# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.domain.catalogue import load_catalogue
from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import component_of
from faint_fuzzies.domain.orbits import OrbitalElements
from faint_fuzzies.domain.orbits import OrbitalElements, _orbit_geometry, ephemeris_step, generate_orbit_diagram, parse_orbits
from faint_fuzzies.media_pool import matched_orbits, orbit_cache_path, orbit_stem

DATA = Path("data")


def _elements(wds_id, designation, period=100.0, unit="y"):
    return OrbitalElements(wds_id=wds_id, designation=designation, period=period, period_unit=unit,
                           semi_major_axis=1.0, inclination=60.0, node=30.0, periastron=1950.0,
                           eccentricity=0.3, periastron_longitude=45.0, grade=3)


def solutions_by_pair(wds_catalogue, orbit_entries):
    """`orbit_entries` is a list of (wds id, designation, period unit); returns "label component" (for
    example "BU17 ac") -> [(file name, title, number)] for the pairs of the WDS catalogue that got a
    plottable solution."""
    collection = Collection([load_catalogue(Path(wds_catalogue))])
    elements = [_elements(wds_id, designation, unit=unit) for wds_id, designation, unit in orbit_entries]
    labels = {id(obj): obj.label for obj in collection.objects}
    keys = {id(obj): f"{obj.label} {component_of(obj)}" for obj in collection.objects}
    found = {}
    for object_id, solutions in matched_orbits(collection, elements).items():
        found[keys[object_id]] = [
            (orbit_cache_path(DATA, s).name, s.title, s.number) for s in solutions]
    return found


def stem_of(name, component, number=None):
    """The file name (without .jpg) of a pair's orbit diagram."""
    return orbit_stem(name, component, None if number in (None, "") else int(number))


_ERRORS = ((93, "0.5"), (115, "0.02"), (134, "1.5"), (153, "2.0"), (175, "0.3"), (195, "0.01"), (214, "3.0"))


def orbit_details(wds_id, designation, unit):
    """What the parser keeps of a line with the errors filled in and the axis in milliarcseconds: the unit code,
    the axis as written and the seven errors."""
    text = orbits_file_text([(wds_id, designation, unit)], errors=True)
    (elements,) = parse_orbits(text)
    return {"unit": elements.semi_major_axis_unit, "axis": elements.semi_major_axis,
            "errors": [elements.period_error, elements.semi_major_axis_error, elements.inclination_error,
                       elements.node_error, elements.periastron_error, elements.eccentricity_error,
                       elements.periastron_longitude_error]}


def draw_orbit(wds_id, designation, unit):
    """Draws the diagram of a line into a temporary file, for the year 2025; returns its size in pixels."""
    import tempfile
    from PIL import Image
    (elements,) = parse_orbits(orbits_file_text([(wds_id, designation, unit)], errors=True))
    destination = Path(tempfile.mkdtemp()) / "orbit.jpg"
    if not generate_orbit_diagram(elements, "Test", destination, year=2025):
        raise AssertionError("no diagram was written")
    return list(Image.open(destination).size)


def orbits_file_text(entries, errors=False, header_lines=7):
    """The text of a minimal orbits.txt: `header_lines` blank header lines (real ones are never blank, but
    a data line is recognized by its own shape, not by what precedes it - see domain.orbits._DATA_LINE) and
    one fixed-width line per entry, each a (WDS id, designation, period unit) as in solutions_by_pair; the
    other elements are always valid."""
    def line(wds_id, designation, unit):
        cells = [" "] * 234
        for start, text in ((0, "000000.00+000000.0"), (19, wds_id.removeprefix("WDS")), (30, designation),
                            (80, "100.0"), (92, unit),
                            (105, "1.0"), (114, "a"), (125, "60.0"), (143, "30.0"), (162, "1950.0"),
                            (174, "y"), (187, "0.3"), (205, "45.0"), (233, "3")) + (
                (((114, "m"),) + _ERRORS) if errors else ()):
            cells[start:start + len(text)] = text
        return "".join(cells)
    return "\n".join([""] * header_lines + [line(*entry) for entry in entries]) + "\n"


def count_with_header_lines(header_lines, entries):
    """How many entries :func:`parse_orbits` finds in a file built with `header_lines` header lines, to
    show that the number of them does not matter."""
    return len(parse_orbits(orbits_file_text(entries, header_lines=int(header_lines))))


def step_of(period, semi_major_axis, eccentricity, inclination, node, periastron, omega, year=2026):
    """The years between two rows of a diagram's table of positions, for the elements given."""
    elements = OrbitalElements(wds_id="WDS00000+0000", designation="X 1", period=float(period), period_unit="y",
                               semi_major_axis=float(semi_major_axis), inclination=float(inclination),
                               node=float(node), periastron=float(periastron), eccentricity=float(eccentricity),
                               periastron_longitude=float(omega), grade=2)
    return ephemeris_step(elements, float(year))


def red_pixels(wds_id, designation, unit):
    """How many clearly red pixels the diagram of a line has: today's position and its year are drawn in red."""
    import tempfile
    from PIL import Image
    (elements,) = parse_orbits(orbits_file_text([(wds_id, designation, unit)], errors=True))
    destination = Path(tempfile.mkdtemp()) / "orbit.jpg"
    generate_orbit_diagram(elements, "Test", destination, year=2025)
    pixels = Image.open(destination).convert("RGB").getdata()
    return sum(1 for r, g, b in pixels if r > 200 and g < 80 and b < 80)


def table_rows(period, semi_major_axis, eccentricity, inclination, node, periastron, omega):
    """The rows of the table of positions a diagram draws (year, separation, position angle as text), for 2026."""
    seen = []
    elements = OrbitalElements(wds_id="WDS00000+0000", designation="X 1", period=float(period), period_unit="y",
                               semi_major_axis=float(semi_major_axis), inclination=float(inclination),
                               node=float(node), periastron=float(periastron), eccentricity=float(eccentricity),
                               periastron_longitude=float(omega), grade=2)
    import tempfile
    from matplotlib.axes import Axes
    real_table = Axes.table

    def spy(self, *args, **kwargs):
        seen.append(kwargs.get("cellText"))
        return real_table(self, *args, **kwargs)

    Axes.table = spy
    try:
        generate_orbit_diagram(elements, "Test", Path(tempfile.mkdtemp()) / "orbit.jpg", year=2026)
    finally:
        Axes.table = real_table
    return [list(row) for row in seen[1][1:]]  # the second table is the one of positions; without its header


def separation_decimals(*elements):
    """How many decimals the separations of a diagram's table have."""
    return len(table_rows(*elements)[0][1].split(".")[1])


def years_of_table(*elements):
    return [row[0] for row in table_rows(*elements)]


def marked_position_count(period, semi_major_axis, eccentricity, inclination, node, periastron, omega, year=2026):
    """How many labeled positions (other than today's) the diagram's orbit curve carries: 3 (quarters) for an
    orbit seen edge-on (85 < inclination < 95), 5 (sixths) otherwise."""
    elements = OrbitalElements(wds_id="WDS00000+0000", designation="X 1", period=float(period), period_unit="y",
                               semi_major_axis=float(semi_major_axis), inclination=float(inclination),
                               node=float(node), periastron=float(periastron), eccentricity=float(eccentricity),
                               periastron_longitude=float(omega), grade=2)
    geometry = _orbit_geometry(elements, int(year))
    return sum(1 for point in geometry.points if point[4] is not None)
