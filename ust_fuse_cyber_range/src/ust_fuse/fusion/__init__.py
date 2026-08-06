"""Fusion pipelines: naive *Reference* vs *Full UST-Fuse*."""
from __future__ import annotations

from typing import Dict

from .base import FusionOutput, build_frames
from .reference import ReferenceFusion
from .ust_fuse import USTFuse

_MODES = {
    "reference": ReferenceFusion,
    "ust_fuse": USTFuse,
}


def build_fusion(mode: str):
    if mode not in _MODES:
        raise ValueError(f"unknown fusion mode {mode!r}; choose from {list(_MODES)}")
    return _MODES[mode]()


def available_modes():
    return list(_MODES)


__all__ = [
    "FusionOutput",
    "build_frames",
    "ReferenceFusion",
    "USTFuse",
    "build_fusion",
    "available_modes",
]
