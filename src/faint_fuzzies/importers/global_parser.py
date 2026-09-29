"""The Global format: twelve fields per line, no header.

name; component; object type; instrument; magnification; sketches; filter; description; difficulty;
SQM-L; SQM-L near the object; rating (for Deep Sky With Binoculars). The name may be a comma-separated
list of several names for the same star or object, any one matching is enough (see
importers.attach.match_any_name). For a double star, the component may be empty, an exact component
text, or "*" for more than one component, the same as the Double Stars format - see importers.attach
for how a row finds its Object from the name and component.
Object types use their own codes, difficulties are German words, and a telescope is named by its
aperture, which the file "optics.json" next to the observer's file translates into an optic code. The
description is used for both languages. Sketches are in "sketches/" next to the file. The filter is one
of FILTERS' keys, or empty - never arbitrary text, to catch a typo rather than publish it.
"""
import json
from pathlib import Path

from faint_fuzzies.domain.findings import Finding
from faint_fuzzies.domain.model import ObjectAttribute, ObservationAttribute
from faint_fuzzies.domain.model import ObjectType as T
from faint_fuzzies.domain.observation import Color, Difficulty, Optic, OpticType, VisibilityEntry, parse_optic
from faint_fuzzies.domain.observer import Observer
from faint_fuzzies.importers.common import (
    RATING_MAP,
    Candidate,
    Row,
    RowReport,
    build_community_observation,
    file_list,
    missing_files,
    parse_instrument,
    source_name,
    tidied_text,
)

OBJECT_TYPES = {
    "V": T.VARIABLE_STAR, "SM": T.ASTERISM, "OS": T.OPEN_CLUSTER, "SW": T.OPEN_CLUSTER, "KS": T.GLOBULAR_CLUSTER,
    "PN": T.PLANETARY_NEBULA, "BN": T.BRIGHT_NEBULA, "DN": T.DARK_NEBULA, "SNR": T.BRIGHT_NEBULA, "GX": T.GALAXY,
    "GXGR": T.GALAXY_GROUP, "QU": T.QUASAR,
}
DIFFICULTIES = {
    "einfach": Difficulty.EASY, "mittel": Difficulty.MEDIUM, "schwer": Difficulty.HARD,
    "nicht gesehen": Difficulty.FAILED, "rot": Color.RED, "orange": Color.ORANGE,
}
FILTERS = {"U": "UHC", "O": "OIII", "H": "HBeta"}
OPTICS_FILE = "optics.json"


def parse_global(rows: list[Row], path: Path, observer: Observer, findings: list[Finding]) -> list[Candidate]:
    """Parses the rows of a Global format file into Candidates; a row with a finding is reported and left out.

    :param rows: the file's non-empty rows, as :func:`faint_fuzzies.importers.common.read_rows` gives them
    :param path: the file's path, used to resolve "sketches/" and the optics file next to it
    :param observer: the observer the file belongs to
    :param findings: the list a row's findings are appended to
    :returns: the understood rows, each as a Candidate
    """
    optics = _optics(path.parent / OPTICS_FILE)
    candidates = []
    for row in rows:
        report = RowReport(source_name(path), row.line, findings)
        if len(row.fields) != 12:
            report.error(None, f"expected 12 fields, found {len(row.fields)}")
            continue
        (name, component, type_text, instrument, magnification, files, filter_text,
         description, difficulty, sqml, sqml_near, rating_text) = [f.strip() for f in row.fields]
        report.label = name or None

        if not name:
            report.error(ObjectAttribute.NAME, "no object named")
        double_star = type_text.upper() == "DS"
        object_type = None
        if not double_star:
            object_type = OBJECT_TYPES.get(type_text.upper())
            if object_type is None:
                report.error(ObjectAttribute.TYPE, f"unknown object type '{type_text}'")
        if rating_text.replace(" ", "") not in RATING_MAP:
            report.error(ObjectAttribute.RATING, f"invalid rating '{rating_text}'")

        optic = _optic(instrument, optics)
        if optic is None:
            report.error(ObservationAttribute.OPTIC,
                        f"unknown instrument '{instrument}' (telescopes are named in {OPTICS_FILE} next to the file)")
        result = None
        if difficulty:
            result = DIFFICULTIES.get(difficulty.lower())
            if result is None:
                report.error(ObservationAttribute.VISIBILITY, f"unknown difficulty '{difficulty}'")
        if filter_text and filter_text not in FILTERS:
            report.error("FILTER", f"unknown filter '{filter_text}' (choose from {', '.join(FILTERS)})")
        if magnification and not magnification.isdigit():
            report.error("MAGNIFICATION", f"invalid magnification '{magnification}'")
        readings = {}
        for attribute, text in ((ObservationAttribute.SQML, sqml), (ObservationAttribute.SQML_LOCAL, sqml_near)):
            if text:
                try:
                    readings[attribute] = str(float(text))
                except ValueError:
                    report.error(attribute, f"invalid number '{text}'")

        images = file_list(files)
        folder = path.parent / "sketches"
        for image in missing_files(images, folder):
            report.error(ObservationAttribute.SKETCH, f"file '{image}' not found in {folder.name}/")
        if report.failed:
            continue
        assert optic is not None  # guaranteed above: the OPTIC check sets report.failed otherwise

        telescope = optic.type is OpticType.TELESCOPE
        filter_name = FILTERS.get(filter_text)
        magnification_value = int(magnification) if telescope and magnification else None
        entries: tuple[VisibilityEntry, ...] = ()
        record = {ObservationAttribute.OPTIC: optic.code}
        if result is not None or filter_name or magnification_value:
            entries = (VisibilityEntry(magnification_value, result, filter_name),)
            parts = [str(magnification_value or "") if telescope else None,
                     result.value if result else "", filter_name or ""]
            record[ObservationAttribute.VISIBILITY] = ",".join(p for p in parts if p is not None).rstrip(",")
        record.update(readings)
        if images:
            record[ObservationAttribute.SKETCH] = ",".join(images)
        text = tidied_text(description)
        if text:
            record[ObservationAttribute.DESCRIPTION_DE] = record[ObservationAttribute.DESCRIPTION_EN] = text
        observation = build_community_observation(record, optic, entries, observer, "visual",
                                                    RATING_MAP[rating_text.replace(" ", "")], "",
                                                    f"{source_name(path)}:{row.line}")
        candidates.append(Candidate(row.line, name, component, object_type, double_star, observation))
    return candidates


def _optic(instrument: str, table: dict[str, str]) -> Optic | None:
    """The optic an instrument field names: a binoculars or naked-eye spec parsed directly, or a telescope
    aperture looked up in `table` (optics.json's aperture -> optic code mapping).

    :param instrument: the instrument field's text
    :param table: the aperture -> optic code mapping of optics.json, or empty when it could not be read
    :returns: the optic, or None when it cannot be resolved
    """
    optic = parse_instrument(instrument)
    if optic is not None and optic.type is not OpticType.TELESCOPE:
        return optic
    code = table.get(instrument)
    if code is None:
        return optic if optic is not None and not table else None
    try:
        return parse_optic(code)
    except ValueError:
        return None


def _optics(path: Path) -> dict[str, str]:
    """The aperture -> optic code mapping of optics.json, or empty when the file is missing or invalid.

    :param path: the optics.json file's path
    :returns: the mapping, or an empty dict when it cannot be read as a JSON object
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): v for k, v in data.items()} if isinstance(data, dict) else {}
