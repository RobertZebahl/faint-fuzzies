# pylint: disable=invalid-name  # module name must match the keyword-library class name (PascalCase)
import os
from pathlib import Path

from PIL import Image

from faint_fuzzies.domain.dss import write_thumbnail


def make_image(path, size=300):
    """Writes a small JPEG (a square) to `path`, making the folder."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (int(size), int(size)), (90, 90, 120)).save(path, format="JPEG")


def make_thumbnail(source, destination):
    """Writes a real, current thumbnail of `source` to `destination` via the production code (see
    domain.dss.write_thumbnail) - for simulating one the live app already made, before a build runs."""
    write_thumbnail(Path(source), Path(destination))


def is_link(path):
    return os.path.islink(path)


def link_target(path):
    return os.readlink(path)


def image_size(path):
    with Image.open(path) as image:
        return list(image.size)
