"""Figure registry: one module per figure type, each exposing ``draw(dataset)``."""
from __future__ import annotations

from collections import OrderedDict

from . import alluvial, design_flow, dumbbell, fishbone, governance, heatmap, roadmap, timeline

_MODULES = (design_flow, timeline, dumbbell, heatmap, governance, alluvial, fishbone, roadmap)

FIGURES = OrderedDict((m.NAME, m) for m in _MODULES)


def get(name):
    try:
        return FIGURES[name]
    except KeyError:
        raise KeyError("unknown figure %r; available: %s" % (name, ", ".join(FIGURES)))
