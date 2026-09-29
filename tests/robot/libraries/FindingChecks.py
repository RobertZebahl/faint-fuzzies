# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
"""Loads a data directory the way the app does and says what the Findings of it are, by Object."""
import json
from pathlib import Path

from faint_fuzzies.domain.filters import FilterSpec, invalid_objects
from faint_fuzzies.loading import load_data_dir, load_static_catalogues


def load_finding_world(data_dir):
    """The valid and the Invalid Objects of the own catalogue, the Findings of each as (severity, attribute,
    observation, message) by the Object's label, and the Findings that belong to no Object."""
    root = Path(data_dir)
    data = load_data_dir(root, load_static_catalogues(root))
    own = data.collection.catalogues[0]
    everything = [*own.objects, *own.invalid]
    return {
        "valid": [o.label for o in own.objects],
        "invalid": [o.label for o in own.invalid],
        "in_collection": [o.label for o in data.collection.objects if o.catalogue == own.name],
        "severity": {o.label: data.findings.severity(o) for o in everything},
        "findings": {o.label: [(p.severity, p.attribute, p.observation, p.message)
                               for p in data.findings.get_findings(o)]
                     for o in everything},
        "left_out_observations": {o.label: [n for n, _raw in o.invalid_observations] for o in own.objects},
        "raw": {o.label: o.raw for o in own.invalid if o.raw is not None},
        "general": [(p.catalogue, p.severity, p.message) for p in data.findings.general],
    }


def invalid_matches(data_dir, spec):
    """The labels of the Invalid Objects a filter shows (`spec` is the JSON of the filter specification)."""
    root = Path(data_dir)
    data = load_data_dir(root, load_static_catalogues(root))
    found = invalid_objects(data.collection, FilterSpec.from_dict(json.loads(spec)), data.references, data.observers,
                            data.findings)
    return [o.label for o in found]
