# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
_ERRORS = ((93, "0.5"), (115, "0.02"), (134, "1.5"), (153, "2.0"), (175, "0.3"), (195, "0.01"), (214, "3.0"))


def orbits_file_text(entries, errors=False, header_lines=7):
    """The text of a minimal orbits.txt: `header_lines` blank header lines (real ones are never blank, but
    a data line is recognized by its own shape, not by what precedes it - see domain.orbits._DATA_LINE) and
    one fixed-width line per entry, each a (WDS id, designation, period unit); the other elements are always
    valid. The unit tests build the same text with tests/unit/builders.py's orbits_file_text."""
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
