"""Sphinx configuration for the faint-fuzzies API documentation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

project = "faint-fuzzies"
copyright = "Robert Zebahl"  # noqa: A001  (standard Sphinx config name)
author = "Robert Zebahl"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
]

# docstrings are plain reST (:param:, :returns:, ...); types are pulled from the signature's annotations
# instead of being repeated by hand, and shown alongside each parameter/return description
autodoc_typehints = "description"
autodoc_member_order = "bysource"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]
