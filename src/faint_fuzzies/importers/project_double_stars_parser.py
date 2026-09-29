"""The Double Stars community format: nine fields per line, no header.

name; component; rating; instrument; magnification; sketches or photographs; description (German);
description (English); notes (private, optional). The component may be empty, an exact component text,
or "*" for more than one component - see importers.attach for how a row finds its Object from these two
fields. "visual.csv" holds visual observations with sketches in "sketches/", "photographic.csv"
photographs in "photographs/", both next to the file.
"""
from pathlib import Path

from faint_fuzzies.domain.findings import Finding
from faint_fuzzies.domain.model import ObjectAttribute, ObservationAttribute
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.importers.common import (
    RATING_MAP,
    Candidate,
    Row,
    RowReport,
    build_community_observation,
    build_descriptions,
    file_list,
    magnification_entry,
    missing_files,
    parse_instrument,
    source_name,
)


def parse_double_stars(rows: list[Row], path: Path, observer: Observer, visual: bool,
                       findings: list[Finding]) -> list[Candidate]:
    """Parses the rows of a Double Stars file into Candidates; a row with a finding is reported and left out.

    :param rows: the file's non-empty rows, as :func:`faint_fuzzies.importers.common.read_rows` gives them
    :param path: the file's path, used to resolve "sketches/" or "photographs/" next to it
    :param observer: the observer the file belongs to
    :param visual: whether the file is visual.csv (sketches, an instrument required) rather than
        photographic.csv (photographs, no instrument)
    :param findings: the list a row's findings are appended to
    :returns: the understood rows, each as a Candidate
    """
    candidates = []
    for row in rows:
        report = RowReport(source_name(path), row.line, findings)
        if len(row.fields) not in (8, 9):
            report.error(None, f"expected 8 or 9 fields, found {len(row.fields)}")
            continue
        fields = [f.strip() for f in row.fields]
        name, component, rating_text, instrument, magnification, files, german, english = fields[:8]
        notes = fields[8] if len(fields) == 9 else ""
        report.label = name or None

        if not name:
            report.error(ObjectAttribute.NAME, "no double star named")
        if rating_text.replace(" ", "") not in RATING_MAP:
            report.error(ObjectAttribute.RATING, f"invalid rating '{rating_text}'")

        optic = parse_instrument(instrument) if instrument else None
        if instrument and optic is None:
            report.error(ObservationAttribute.OPTIC, f"invalid instrument '{instrument}'")
        elif optic is None and visual:
            report.error(ObservationAttribute.OPTIC, "no instrument given")
        if visual and magnification and not magnification.isdigit():
            report.error("MAGNIFICATION", f"invalid magnification '{magnification}'")

        images = file_list(files)
        folder = path.parent / ("sketches" if visual else "photographs")
        media_attribute = ObservationAttribute.SKETCH if visual else ObservationAttribute.PHOTOGRAPH
        for image in missing_files(images, folder):
            report.error(media_attribute, f"file '{image}' not found in {folder.name}/")
        german, english = build_descriptions(german, english)
        if not german and not english and not images:
            report.error(ObservationAttribute.DESCRIPTION, "neither a description nor an image given")
        if report.failed:
            continue

        visibility = magnification_entry(optic, magnification if visual else "")
        record = {}
        if optic:
            record[ObservationAttribute.OPTIC] = optic.code
        if visibility:
            record[ObservationAttribute.VISIBILITY] = str(visibility[0].magnification)
        if images:
            record[media_attribute] = ",".join(images)
        if german:
            record[ObservationAttribute.DESCRIPTION_DE] = german
        if english:
            record[ObservationAttribute.DESCRIPTION_EN] = english
        observation = build_community_observation(record, optic, visibility, observer,
                                                    "visual" if visual else "photographic",
                                                    RATING_MAP[rating_text.replace(" ", "")], notes,
                                                    f"{source_name(path)}:{row.line}")
        candidates.append(Candidate(row.line, name, component, None, True, observation))
    return candidates
