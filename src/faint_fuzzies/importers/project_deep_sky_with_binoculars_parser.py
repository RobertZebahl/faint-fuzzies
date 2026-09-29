"""The Deep Sky With Binoculars community format: twelve fields per line, no header.

name; object type; rating; instrument; Bortle; SQM; SQM-L; limiting magnitude; visibility;
sketches; description (German); description (English); notes (private, optional). The name may be a
comma-separated list of several names for the same object, any one matching is enough (see
importers.attach.match_any_name).
Sketches are in "sketches/" next to the file. Only binoculars and the naked eye are accepted, and at least
one condition is required. Any text in the visibility column means the object was not seen.
"""
import re
from pathlib import Path

from faint_fuzzies.domain.findings import Finding
from faint_fuzzies.domain.model import ObjectAttribute, ObjectType, ObservationAttribute
from faint_fuzzies.domain.observation import Difficulty, OpticType, VisibilityEntry
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.importers.common import (
    RATING_MAP,
    Candidate,
    Row,
    RowReport,
    build_community_observation,
    build_descriptions,
    file_list,
    missing_files,
    parse_instrument,
    source_name,
)

_BORTLE = re.compile(r"\d[+-]?")
_LIMITING_MAGNITUDE = re.compile(r"\d+(?:\.\d+)?\+?")


def parse_deep_sky_binoculars(rows: list[Row], path: Path, observer: Observer,
                              findings: list[Finding]) -> list[Candidate]:
    """Parses the rows of a Deep Sky With Binoculars file into Candidates; a row with a finding is reported
    and left out.

    :param rows: the file's non-empty rows, as :func:`faint_fuzzies.importers.common.read_rows` gives them
    :param path: the file's path, used to resolve "sketches/" next to it
    :param observer: the observer the file belongs to
    :param findings: the list a row's findings are appended to
    :returns: the understood rows, each as a Candidate
    """
    candidates = []
    for row in rows:
        report = RowReport(source_name(path), row.line, findings)
        if len(row.fields) not in (12, 13):
            report.error(None, f"expected 12 or 13 fields, found {len(row.fields)}")
            continue
        fields = [f.strip() for f in row.fields]
        (name, type_text, rating_text, instrument, bortle, sqm, sqml, limiting, visibility, files, german,
         english) = fields[:12]
        notes = fields[12] if len(fields) == 13 else ""
        report.label = name or None

        if not name:
            report.error(ObjectAttribute.NAME, "no object named")
        object_type = None
        if type_text:
            try:
                object_type = ObjectType.parse(type_text)
            except ValueError as exc:
                report.error(ObjectAttribute.TYPE, str(exc))
        if rating_text.replace(" ", "") not in RATING_MAP:
            report.error(ObjectAttribute.RATING, f"invalid rating '{rating_text}'")

        optic = parse_instrument(instrument)
        if optic is None or optic.type is OpticType.TELESCOPE:
            report.error(ObservationAttribute.OPTIC,
                        f"binoculars (8x40) or the naked eye (A) expected, found '{instrument}'")
        if bortle and not _BORTLE.fullmatch(bortle):
            report.error(ObservationAttribute.BORTLE, f"invalid Bortle class '{bortle}'")
        sqm_value = _number(report, ObservationAttribute.SQM, sqm)
        sqml_value = _number(report, ObservationAttribute.SQML, sqml)
        if limiting and not _LIMITING_MAGNITUDE.fullmatch(limiting):
            report.error(ObservationAttribute.NELM, f"invalid limiting magnitude '{limiting}'")
        if not (bortle or sqm or sqml or limiting):
            report.error(ObservationAttribute.BORTLE,
                        "no conditions given; at least one of Bortle, SQM, SQM-L and limiting magnitude is required")

        seen = not visibility
        images = file_list(files)
        folder = path.parent / "sketches"
        for image in missing_files(images, folder):
            report.error(ObservationAttribute.SKETCH, f"file '{image}' not found in {folder.name}/")
        german, english = build_descriptions(german, english)
        if seen and not german and not english and not images:
            report.error(ObservationAttribute.DESCRIPTION, "neither a description nor an image given")
        if report.failed:
            continue
        assert optic is not None  # guaranteed above: the OPTIC check sets report.failed otherwise

        record = {ObservationAttribute.OPTIC: optic.code}
        if bortle:
            record[ObservationAttribute.BORTLE] = bortle
        if sqm_value is not None:
            record[ObservationAttribute.SQM] = str(sqm_value)
        if sqml_value is not None:
            record[ObservationAttribute.SQML] = str(sqml_value)
        if limiting:
            record[ObservationAttribute.NELM] = (f"{float(limiting[:-1])}+" if limiting.endswith("+")
                                                 else str(float(limiting)))
        entries: tuple[VisibilityEntry, ...] = ()
        if not seen:
            record[ObservationAttribute.VISIBILITY] = Difficulty.FAILED.value
            entries = (VisibilityEntry(None, Difficulty.FAILED, None),)
        if images:
            record[ObservationAttribute.SKETCH] = ",".join(images)
        if german:
            record[ObservationAttribute.DESCRIPTION_DE] = german
        if english:
            record[ObservationAttribute.DESCRIPTION_EN] = english
        observation = build_community_observation(record, optic, entries, observer, "visual",
                                                    RATING_MAP[rating_text.replace(" ", "")], notes,
                                                    f"{source_name(path)}:{row.line}")
        candidates.append(Candidate(row.line, name, "", object_type, False, observation))
    return candidates


def _number(report: RowReport, attribute: str, text: str) -> float | None:
    """Parses a numeric field, reporting an error on `report` when it is given but not a valid number.

    :param report: the row's report, an invalid number is reported to it
    :param attribute: the attribute the field belongs to, for the error
    :param text: the field's text
    :returns: the parsed number, or None when the field is empty or invalid
    """
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        report.error(attribute, f"invalid number '{text}'")
        return None
