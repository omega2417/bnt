"""LexViz - Legal-Administrative Visualisation Toolkit.

Turns one provenance-tagged dataset (YAML/JSON) into publication-ready
figures for research in public administration and justice.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .data import DataError, load, validate  # noqa: F401
from .build import build  # noqa: F401
