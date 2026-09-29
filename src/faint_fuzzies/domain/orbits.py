"""Orbit diagrams: a generated plot of a WDS pair's computed orbit, from published orbital elements (the
Sixth Catalog of Orbits of Visual Binary Stars, orbits.txt). Parsed at runtime only - never converted
into a stored catalogue, since orbital elements are inputs to one plot for one system, not reference data
other Objects link against.
"""
import datetime
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faint_fuzzies.domain.collection import Collection
from faint_fuzzies.domain.names import PAIR, component_of

# A data line's first 18 characters are its RA,Dec position, fixed width: 6 digits, ".", two digits or
# spaces (the fractional seconds, sometimes left blank, as in WDS22300+0426's STF2912Ba,Bb record), then
# the declination the same way with a sign. A header, ruler or blank line never looks like that, whatever
# their number - the file has been seen with seven of them (a title, a blank line, three ruler lines, the
# column header, and one more blank) and might one day have a different number.
_DATA_LINE = re.compile(r"^\d{6}\.[0-9 ]{2}[+-]\d{6}\.[0-9 ] ")
# the unit codes of the semi-major axis and how the diagram writes them
_AXIS_UNITS = {"u": r" $\mathrm{\mu}\mathrm{as}$", "m": r" $\mathrm{mas}$", "a": '"', "M": "'"}
_PERIOD_UNITS = {"d": r"$\mathrm{days}$", "y": r"$\mathrm{years}$", "c": r"$\mathrm{centuries}$"}
_DEGREES = r"$\mathrm{\degree}$"


@dataclass(frozen=True)
class OrbitalElements:
    """One published orbital solution for a WDS pair, as one row of orbits.txt describes it. The `_error`
    fields are the published errors of their element, shown as they are in the diagram; each is None when
    the file gives none.

    :ivar wds_id: the WDS identifier
    :ivar designation: the discoverer designation, with any component suffix, e.g. "STF 60AB"
    :ivar period: the orbital period, in `period_unit`
    :ivar period_unit: "d", "y" or "c"
    :ivar semi_major_axis: the semi-major axis, in `semi_major_axis_unit`: the plot is the same in any unit
    :ivar inclination: the inclination, in degrees
    :ivar node: the ascending node (big omega), in degrees
    :ivar periastron: the Besselian year of periastron passage
    :ivar eccentricity: the orbital eccentricity
    :ivar periastron_longitude: the argument of periastron (small omega), in degrees
    :ivar grade: the orbit grade, 1 (definitive) to 5 (indeterminate)
    :ivar semi_major_axis_unit: "u" microarcseconds, "m" milliarcseconds, "a" arcseconds, "M" arcminutes
    """
    wds_id: str
    designation: str
    period: float
    period_unit: str
    semi_major_axis: float
    inclination: float
    node: float
    periastron: float
    eccentricity: float
    periastron_longitude: float
    grade: int | None
    semi_major_axis_unit: str = "a"
    period_error: float | None = None
    semi_major_axis_error: float | None = None
    inclination_error: float | None = None
    node_error: float | None = None
    periastron_error: float | None = None
    eccentricity_error: float | None = None
    periastron_longitude_error: float | None = None


def parse_orbits(text: str) -> list[OrbitalElements]:
    """Parses the valid entries of orbits.txt; a line that is not a data line at all (see :data:`_DATA_LINE`)
    is skipped, and so is one with an unusable unit or a missing element.

    :param text: the full contents of orbits.txt
    :returns: the orbital elements of every valid entry, in file order
    """
    return [e for line in text.splitlines() if _DATA_LINE.match(line) and len(line) >= 234
            for e in [_parse_line(line)] if e]


def _parse_line(line: str) -> OrbitalElements | None:
    """Parses one fixed-width line of orbits.txt into its OrbitalElements, or None when the period or the
    semi-major axis is missing or in an unusable unit, or any of inclination, node, periastron, eccentricity
    or the longitude of periastron is missing.

    :param line: one line of orbits.txt
    :returns: the parsed elements, or None when the line cannot be used
    """
    period = _number(line[80:92])
    if period is None or line[92] not in ("d", "y", "c"):
        return None
    semi_major_axis = _number(line[105:114])
    if semi_major_axis is None or line[114] not in _AXIS_UNITS:
        return None
    inclination = _number(line[125:133])
    node = _number(line[143:151])
    periastron = _number(line[162:174])
    eccentricity = _number(line[187:195])
    periastron_longitude = _number(line[205:213])
    if None in (inclination, node, periastron, eccentricity, periastron_longitude) or line[174] != "y":
        return None
    grade_text = line[233:234].strip()

    return OrbitalElements(
        wds_id=f"WDS{line[19:29].strip()}", designation=line[30:44].strip().replace(",", "-"),
        period=period, period_unit=line[92], semi_major_axis=semi_major_axis,
        inclination=inclination, node=node, periastron=periastron, eccentricity=eccentricity,
        periastron_longitude=periastron_longitude, grade=int(grade_text) if grade_text else None,
        semi_major_axis_unit=line[114], period_error=_number(line[93:104]),
        semi_major_axis_error=_number(line[115:124]), inclination_error=_number(line[134:142]),
        node_error=_number(line[153:161]), periastron_error=_number(line[175:186]),
        eccentricity_error=_number(line[195:203].strip(" -")),
        periastron_longitude_error=_number(line[214:222].lstrip("q").strip()))


def _number(text: str) -> float | None:
    text = text.strip().rstrip(".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def can_plot(elements: OrbitalElements) -> bool:
    """Whether `elements` can be plotted: only orbits with the period already expressed in years, longer
    than six months, are - the mean-motion formula in :func:`_angular_position` assumes years.

    :param elements: the orbital elements to check
    :returns: whether :func:`generate_orbit_diagram` can plot them
    """
    return elements.period_unit == "y" and elements.period > 0.5


def match_pairs(collection: Collection, elements: list[OrbitalElements]) -> dict[int, list[OrbitalElements]]:
    """Matches orbital elements to the WDS-catalogue pairs they belong to: a pair can have several
    published solutions. A WDS id shared by several pairs of one group is disambiguated by the pair's own
    COMPONENT (the discoverer-designation suffix); an entry that still cannot be told apart is left out.

    :param collection: the collection to match pairs against
    :param elements: the orbital elements to match, as parsed by :func:`parse_orbits`
    :returns: id(pair Object) -> all its matched OrbitalElements, in file order
    """
    matched: dict[int, list[OrbitalElements]] = {}
    for entry in elements:
        found = {id(o): o for o in collection.names.lookup(PAIR, entry.wds_id)
                if Path(o.catalogue).stem.casefold() == "wds"}
        candidates = list(found.values())  # lookup() may repeat one Object across several name forms
        if len(candidates) == 1:
            matched.setdefault(id(candidates[0]), []).append(entry)
        elif len(candidates) > 1:
            for candidate in candidates:
                if entry.designation.casefold().endswith(component_of(candidate).casefold()):
                    matched.setdefault(id(candidate), []).append(entry)
                    break
    return matched


def _angular_position(elements: OrbitalElements, epoch: float) -> tuple[float, float]:
    """The apparent position at a Besselian-year epoch, by the standard two-body solution: mean anomaly,
    Kepler's equation solved by fixed-point iteration, true anomaly, then projected onto the sky using
    inclination, node and argument of periastron.

    :param elements: the orbital elements
    :param epoch: the Besselian year to compute the position at
    :returns: the separation in arcseconds and the position angle in radians
    """
    i = math.radians(elements.inclination)
    big_omega = math.radians(elements.node)
    small_omega = math.radians(elements.periastron_longitude)

    mean_anomaly = math.radians((360 / elements.period * (epoch - elements.periastron)) % 360)
    eccentric_anomaly = mean_anomaly
    for _ in range(50):
        eccentric_anomaly = mean_anomaly + elements.eccentricity * math.sin(eccentric_anomaly)

    r = elements.semi_major_axis * (1 - elements.eccentricity * math.cos(eccentric_anomaly))
    true_anomaly = 2 * math.atan(math.sqrt((1 + elements.eccentricity) / (1 - elements.eccentricity))
                                 * math.tan(eccentric_anomaly / 2))

    theta = math.atan2(math.tan(true_anomaly + small_omega) * math.cos(i), 1) + big_omega
    if theta < 0:
        theta += 2 * math.pi
    rho = (r * math.cos(true_anomaly + small_omega)) / math.cos(theta - big_omega)
    if rho < 0:
        rho, theta = -rho, theta + math.pi
    return rho, theta % (2 * math.pi)


# the step of the table of positions is chosen from this; see ephemeris_step
_SHORT_STEPS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5)
_LONG_STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000)
_TABLE_ROWS = 11
_VISIBLE_CHANGE = 0.05  # the table has to show the separation change by 5 % or the position angle by 5 degrees


def ephemeris_step(elements: OrbitalElements, year: float) -> float:
    """The years between two rows of the table of positions, so that the table tells something about the
    pair: a pair with a period under 10 years gets the largest of the fine steps that is at most a tenth of
    the period, so the table covers about one revolution; any other pair gets one year unless the separation
    and position angle hardly change in ten of them, and then the smallest longer step at which they change
    visibly, but never more than a tenth of the period.

    :param elements: the orbital elements
    :param year: the year the table starts from
    :returns: the step, in years, between consecutive rows of the table
    """
    period = elements.period
    if period < 10:
        return ([step for step in _SHORT_STEPS if step <= period / 10] or [_SHORT_STEPS[0]])[-1]
    rho_0, theta_0 = _angular_position(elements, year)
    last = 1
    for step in _LONG_STEPS:
        if step > period / 10:
            break
        last = step
        changes = []
        for row in range(1, _TABLE_ROWS):
            rho, theta = _angular_position(elements, year + row * step)
            changes.append((abs(rho - rho_0) / rho_0 if rho_0 else 0.0,
                            abs((math.degrees(theta - theta_0) + 180) % 360 - 180)))
        if any(rho_change >= _VISIBLE_CHANGE or theta_change >= _VISIBLE_CHANGE * 100
               for rho_change, theta_change in changes):
            return step
    return last


@dataclass(frozen=True)
class _OrbitGeometry:
    """The orbit curve and its marked positions, projected onto the sky and scaled to fit the plot.

    :ivar points: the curve's 128 points, plus one labeled point per marked position (x, y, dx, dy, year);
        a plain curve point's dx/dy/year are all None
    :ivar now: today's labeled position (x, y, dx, dy, year)
    :ivar x_offset: added to every x so the primary (always at x=0) is in view
    :ivar y_offset: added to every y so the primary (always at y=0) is in view
    :ivar x_scale: multiplies every offset x into the plot's 0-1 range
    :ivar y_scale: multiplies every offset y into the plot's 0-1 range
    """
    points: list[tuple[float, float, float | None, float | None, float | None]]
    now: tuple[float, float, float, float, float]
    x_offset: float
    y_offset: float
    x_scale: float
    y_scale: float


def _orbit_geometry(elements: OrbitalElements, year: int) -> _OrbitGeometry:
    """The projected, scaled orbit curve and its marked positions.

    :param elements: the orbital elements
    :param year: the year the first marked position (today's, drawn in red by :func:`_draw_orbit`) is at
    :returns: the geometry :func:`_draw_orbit` draws
    """
    def projected(_rho: float, _theta: float) -> tuple[float, float]:
        _x, _y = _rho * math.cos(_theta), _rho * math.sin(_theta)
        return _y, -_x  # east to the right, north down: the labels N (below) and W (left) say so

    n = 128
    epoch = elements.periastron
    points: list[tuple[float, float, float | None, float | None, float | None]] = []
    for _ in range(n):
        x, y = projected(*_angular_position(elements, epoch))
        points.append((x, y, None, None, None))
        epoch += elements.period / n
    xs, ys = [p[0] for p in points], [p[1] for p in points]

    # the positions to mark: from this year on, in sixths of the period (in quarters for an orbit seen edge-on),
    # rounded to whole years unless the period is short; the first one is today's, which is drawn in red
    edge_on = 85 < elements.inclination < 95
    fractions = [0, 3 / 12, 6 / 12, 9 / 12] if edge_on else [0, 1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6]
    marked = [year + elements.period * fraction for fraction in fractions]
    marked = [int(e) for e in marked] if elements.period > 6 else [round(e, 1) for e in marked]

    def position_and_direction(_e: float) -> tuple[float, float, float, float]:
        _x, _y = projected(*_angular_position(elements, _e))
        _epsilon = elements.period / 2 ** 16
        _dx = _dy = 0.0
        while _dx == 0 and _dy == 0:
            before_x, before_y = projected(*_angular_position(elements, _e - _epsilon))
            _dx, _dy = _x - before_x, _y - before_y
            _epsilon *= 2
        return _x, _y, _dx, _dy

    points.extend((*position_and_direction(e), e) for e in marked[1:])
    now = (*position_and_direction(float(year)), float(year))

    x_min, x_max = min(0.0, *xs), max(0.0, *xs)  # the primary, at (0, 0), is always in view
    y_min, y_max = min(0.0, *ys), max(0.0, *ys)
    x_offset, y_offset = -x_min, -y_min
    x_scale = 1 / (x_max - x_min) if x_max > x_min else 1.0
    y_scale = 1 / (y_max - y_min) if y_max > y_min else 1.0

    return _OrbitGeometry(points, now, x_offset, y_offset, x_scale, y_scale)


def _draw_orbit(ax: Any, elements: OrbitalElements, title: str, geometry: _OrbitGeometry) -> None:
    """Draws the title, the primary, the N/W axes, the orbit curve with its marked positions, and today's
    position in red.

    :param ax: the axes to draw onto
    :param elements: the orbital elements being plotted
    :param title: the title the diagram is drawn with
    :param geometry: the orbit's geometry, as computed by :func:`_orbit_geometry`
    """
    x_offset, y_offset = geometry.x_offset, geometry.y_offset
    x_scale, y_scale = geometry.x_scale, geometry.y_scale

    ax.text(0, 1.3, title, fontsize=24, weight="bold", va="center", ha="left")
    ax.text(0, 1.175, f"Apparent Orbit (scaling ratio x:y = {x_scale / y_scale:.2f})",
            fontsize=12, va="center", ha="left")
    ax.plot(x_offset * x_scale, y_offset * y_scale, "ko", markersize=5)  # the primary
    ax.plot([x_offset * x_scale] * 2, [-0.05, 1.05], color="gray", linestyle="-", linewidth=0.4)
    ax.plot([-0.05, 1.05], [y_offset * y_scale] * 2, color="gray", linestyle="-", linewidth=0.4)
    ax.text(x_offset * x_scale, -0.275, "N", ha="center", color="gray")
    ax.text(-0.275, y_offset * y_scale, "W", va="center", color="gray")

    for x, y, dx, dy, e in geometry.points:
        ax.plot((x + x_offset) * x_scale, (y + y_offset) * y_scale, "ko", markersize=4 if e else 1)
        if e:
            assert dx is not None and dy is not None  # set together with e, never individually
            ha, va = _label_alignment(dx, dy, elements.inclination > 90)
            ax.annotate(f"  {e:.1f}  ", ((x + x_offset) * x_scale, (y + y_offset) * y_scale),
                        va=va, ha=ha, fontsize=9, fontweight="bold")

    now_x, now_y, now_dx, now_dy, now_year = geometry.now
    ax.plot((now_x + x_offset) * x_scale, (now_y + y_offset) * y_scale, "o", color="red", markersize=6)
    now_ha, now_va = _label_alignment(now_dx, now_dy, elements.inclination > 90)
    ax.annotate(f"  {now_year:.1f}  ", ((now_x + x_offset) * x_scale, (now_y + y_offset) * y_scale),
                va=now_va, ha=now_ha, fontsize=9, fontweight="bold", color="red")


def _draw_elements_table(ax: Any, elements: OrbitalElements) -> None:
    """Draws the table of the orbital elements, with their errors.

    :param ax: the axes to draw onto
    :param elements: the orbital elements to tabulate
    """
    def with_error(_value: float, _unit: str, _error: float | None) -> list[str]:
        return [f"{_value}{_unit}", f" $\\pm$ {_error}" if _error else ""]

    rows = [
        ["Period (P)", *with_error(elements.period, " " + _PERIOD_UNITS[elements.period_unit], elements.period_error)],
        ["Eccentricity (e)", *with_error(elements.eccentricity, "", elements.eccentricity_error)],
        [r"Node ($\mathrm{\Omega}$)", *with_error(elements.node, _DEGREES, elements.node_error)],
        ["Periastron (T)", *with_error(elements.periastron, "", elements.periastron_error)],
        ["Inclination (i)", *with_error(elements.inclination, _DEGREES, elements.inclination_error)],
        ["Semi-major axis (a)", *with_error(elements.semi_major_axis, _AXIS_UNITS[elements.semi_major_axis_unit],
                                            elements.semi_major_axis_error)],
        [r"Longitude of periastron ($\mathrm{\omega}$)",
         *with_error(elements.periastron_longitude, _DEGREES, elements.periastron_longitude_error)],
        ["Grade", str(elements.grade if elements.grade else "-"), "(1=definitive, 5=indeterminate)"],
    ]
    table = ax.table(cellText=rows, edges="open", colWidths=[0.8, 0.4, 0.8], bbox=[0, -0.75, 2.0, 0.55])
    # kept at this fixed size for consistency with existing orbit images; the automatic one is smaller
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for row in range(len(rows)):
        for column in range(3):
            table.get_celld()[row, column].set_text_props(ha="left")


def _draw_ephemeris_table(ax: Any, elements: OrbitalElements, year: int) -> None:
    """Draws the table of positions over time (see :func:`ephemeris_step`).

    :param ax: the axes to draw onto
    :param elements: the orbital elements to tabulate positions for
    :param year: the year the table starts from
    """
    axis_unit = _AXIS_UNITS[elements.semi_major_axis_unit].strip()
    ephemeris = [["Year", rf"$\mathrm{{\rho}}$ [{axis_unit}]", rf"$\mathrm{{\theta}}$ [{_DEGREES}]"]]
    step = ephemeris_step(elements, float(year))
    year_format = "{:.2f}" if step < 1 and round(step * 10) != step * 10 else "{:.1f}"  # 0.25 needs two decimals
    positions = [_angular_position(elements, float(year + row * step)) for row in range(_TABLE_ROWS)]
    # two decimals, or more when the separations are so small that two decimals would hide how they change
    smallest = min(rho for rho, _ in positions)
    decimals = max(2, 1 - math.floor(math.log10(smallest))) if smallest > 0 else 2
    for row, (rho, theta) in enumerate(positions):
        ephemeris.append([year_format.format(year + row * step), f"{rho:.{decimals}f}",
                          f"{math.degrees(theta):.2f}"])
    epoch_table = ax.table(cellText=ephemeris, colWidths=[0.2, 0.3, 0.3], bbox=[1.2, 0.15, 0.8, 0.8])
    for cell in epoch_table.get_celld().values():
        # matplotlib's Cell has no public API to change text alignment after creation
        cell._loc = "center"  # pylint: disable=protected-access
        cell.visible_edges = "B"


def generate_orbit_diagram(elements: OrbitalElements, title: str, destination: Path, year: int | None = None) -> bool:
    """Writes a plot of the apparent orbit to `destination`, styled to match an existing orbit image on disk
    so a reused and a newly generated one stand side by side consistently: the orbit with today's position
    (in red) and the years of the positions a sixth of a period apart after it, a table of the separation
    and position angle over 11 rows (see :func:`ephemeris_step`), the elements with their errors, and the
    source.

    :param elements: the orbital elements to plot
    :param title: the title the diagram is drawn with
    :param destination: the file the diagram is written to; its parent directories are created as needed
    :param year: the year the positions and the table start from; this year when not given
    :returns: whether a file was written; see :func:`can_plot` for when it is not
    """
    if not can_plot(elements):
        return False

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    year = year if year is not None else datetime.datetime.now(datetime.UTC).date().year
    geometry = _orbit_geometry(elements, year)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    _draw_orbit(ax, elements, title, geometry)
    _draw_elements_table(ax, elements)
    _draw_ephemeris_table(ax, elements, year)

    ax.text(0, -1.15, "Data source of orbital elements: http://www.astro.gsu.edu/wds/orb6.html",
            fontsize=9, weight="bold")

    ax.set_aspect("equal")
    ax.set_xlim(-0.05, 1.05)
    ax.axis("off")

    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


def _label_alignment(dx: float, dy: float, retrograde: bool) -> tuple[str, str]:
    """Where a year label sits by its dot, so that it stays clear of the orbit: it depends on the direction
    the star moves in and on the sense of the orbit.

    :param dx: the star's horizontal direction of motion at the label's position
    :param dy: the star's vertical direction of motion at the label's position
    :param retrograde: whether the orbit is retrograde (inclination over 90 degrees)
    :returns: the label's (horizontal alignment, vertical alignment), for matplotlib's annotate
    """
    if dx > 0 and dy > 0:
        return ("right", "bottom") if retrograde else ("left", "top")
    if dy < 0 < dx:
        return ("left", "bottom") if retrograde else ("right", "top")
    if dx < 0 < dy:
        return ("right", "top") if retrograde else ("left", "bottom")
    return ("left", "top") if retrograde else ("right", "bottom")
