# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
from pathlib import Path

from faint_fuzzies.domain.names import component_of
from faint_fuzzies.loading import load_data_dir, load_static_catalogues


def attachments(data_dir):
    """(line of the row in the observer's file, label of the Object it was attached to, its component or None
    for a group), for every community observation of the data directory, by line."""
    root = Path(data_dir)
    data = load_data_dir(root, load_static_catalogues(root, None), None)
    found = []
    for obj in data.collection.objects:
        for observation in obj.community_observations:
            line = int(observation.source.rsplit(":", 1)[1])
            found.append((line if observation.source.startswith("anna-example") else 1000 + line, obj.label,
                          None if obj.is_group else component_of(obj)))
    return sorted(found)
