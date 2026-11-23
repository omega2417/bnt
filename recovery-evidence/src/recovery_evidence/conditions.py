"""Experimental conditions C0-C12 (Table 4), loaded from ``data/conditions.json``.

The JSON file is the single source of every generator and policy parameter.
``recovery-evidence params`` prints the fully resolved configuration.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from importlib import resources
from typing import Dict, List, Tuple

from .topology import DependencyMap, get_map


@dataclass(frozen=True)
class Condition:
    id: int
    name: str
    label: str
    question: str
    T: int
    R: int
    b: int
    p_fail: float
    p_rec: float
    p_report: float
    delay_values: Tuple[int, ...]
    p_nonsubstantive: float
    w: int
    evaluator_map: str
    operator_map: str
    suppressed_components: Tuple[str, ...]
    p_joint: float
    joint_components: Tuple[str, ...]
    root_entropy: int

    def maps(self) -> Tuple[DependencyMap, DependencyMap]:
        """(operator map, evaluator map); both share one component list."""
        op, ev = get_map(self.operator_map), get_map(self.evaluator_map)
        if op.components != ev.components:
            raise ValueError("operator and evaluator maps must list the same components")
        return op, ev

    def with_(self, **changes) -> "Condition":
        return replace(self, **changes)

    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ("delay_values", "suppressed_components", "joint_components"):
            d[key] = list(d[key])
        return d


def load_raw() -> dict:
    text = resources.files("recovery_evidence").joinpath("data/conditions.json").read_text(encoding="utf-8")
    return json.loads(text)


def load_conditions() -> List[Condition]:
    raw = load_raw()
    out = []
    for entry in raw["conditions"]:
        params = dict(raw["defaults"])
        params.update(entry["overrides"])
        for key in ("delay_values", "suppressed_components", "joint_components"):
            params[key] = tuple(params[key])
        out.append(
            Condition(
                id=entry["id"], name=entry["name"], label=entry["label"],
                question=entry["question"], root_entropy=raw["root_entropy"], **params,
            )
        )
    return out


def by_name() -> Dict[str, Condition]:
    return {c.name: c for c in load_conditions()}


def get_condition(name: str) -> Condition:
    return by_name()[name]
