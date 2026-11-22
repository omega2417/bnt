"""Illustrative scenario BNK_PAY (phishing, ATT&CK T1566) and the state generator (12).

Class tables, weights, core set and the E1 values are those of the illustrative
example of CRTM [35-37] (Table A1 of the manuscript). They are NOT field data.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .model import BasicAction, Configuration, Metric

# (code, name, unit, xi, core, step, E1 value, source)
_RAW = {
    ("UN.S1.A1", "Use of shared threat information", "ANT", "Understand"): [
        ("M1", "Number of TI sources used", "sources", (0, 1, 2, 3, 4, 4), True, 1, 4),
        ("M2", "TI update frequency", "events/day", (1, 2, 7, 25, 96, 96), False, None, 96),
        ("M3", "Time to determine TI relevance", "min", (180, 179, 90, 30, 10, 0), False, None, 25),
        ("M4", "Time to disseminate defensive TTPs", "min", (240, 239, 120, 60, 15, 0), False, None, 45),
        ("M5", "External TI sharing frequency", "events/month", (0, 1, 2, 4, 9, 9), False, 1, 4),
        ("M6", "Number of monitored threat types", "types", (0, 1, 2, 3, 5, 5), False, 1, 4),
    ],
    ("UN.S2.A1", "Mission / business impact and crown-jewels analysis", "ANT", "Understand"): [
        ("M1", "Time since last MIA/BIA/CJA update", "min", (777600, 777599, 525600, 262080, 131040, 0), False, None, 705600),
        ("M2", "Degree of MIA/BIA/CJA validation", "rank", (0, 1, 2, 3, 4, 4), False, 1, 4),
        ("M3", "Resources with assigned criticality", "%", (30, 31, 61, 76, 91, 100), False, None, 80),
    ],
    ("CN.S1.A1", "Damage assessment and integrity of critical data", "WITH", "Continue"): [
        ("AM-DA-1", "Time to assess mission damage", "min", (300, 299, 180, 90, 30, 0), False, None, 210),
        ("SI-IC-1", "Time to confirm integrity of critical data", "min", (45, 44, 25, 15, 5, 0), False, None, 18),
        ("SI-IC-2", "Critical data with verifiable integrity", "%", (40, 41, 66, 81, 91, 100), True, None, 85),
        ("M1", "Critical data verified since CCoA start", "%", (30, 31, 51, 71, 91, 100), False, None, 70),
        ("SI-IC-3", "Time to verify security-critical data", "min", (50, 49, 30, 20, 10, 0), False, None, 25),
        ("SI-BV-1", "Time to verify critical service behavior", "min", (70, 69, 45, 30, 15, 0), False, None, 40),
        ("M2", "Critical applications verified since CCoA", "%", (40, 41, 61, 76, 91, 100), False, None, 75),
        ("SI-BV-2", "Time to verify security-critical services", "min", (75, 74, 55, 35, 15, 0), False, None, 55),
        ("M3", "Security-critical software verified since CCoA", "%", (50, 51, 66, 81, 91, 100), False, None, 75),
        ("SI-IC-5", "Software integrity check frequency", "checks/day", (0.2, 0.3, 1, 3, 7, 7), False, None, 4),
    ],
    ("CN.S2.A1", "Continuity of verified data assets and services", "WITH", "Continue"): [
        ("AM-DA-1", "Time to assess mission damage", "min", (300, 299, 180, 90, 30, 0), False, None, 210),
        ("SI-IC-1", "Time to verify critical data", "min", (25, 24, 15, 9, 4, 0), False, None, 7),
        ("SI-IC-2", "Data assets with auditable integrity", "%", (40, 41, 61, 76, 86, 100), True, None, 80),
        ("M1", "Assets verified after CCoA", "%", (35, 36, 56, 71, 86, 100), False, None, 75),
        ("SI-IC-3", "Time to verify security-critical data", "min", (40, 39, 25, 15, 7, 0), False, None, 25),
        ("SI-BV-1", "Time to verify critical services", "min", (70, 69, 45, 30, 15, 0), False, None, 40),
        ("M2", "Applications verified after CCoA", "%", (45, 46, 66, 76, 86, 100), False, None, 83),
        ("SI-BV-2", "Time to verify security services", "min", (35, 34, 20, 12, 5, 0), False, None, 15),
        ("M3", "Security software verified after CCoA", "%", (50, 51, 66, 81, 91, 100), False, None, None),
        ("SI-IC-5", "Software integrity check frequency", "checks/day", (0.2, 0.3, 1, 3, 7, 7), False, None, 1),
    ],
    ("RE.S1.A2", "Restoration of information integrity", "REC", "Reconstitute"): [
        ("SI-IC-2", "Mission-critical data with confirmed integrity", "%", (50, 51, 71, 86, 96, 100), False, None, 90),
        ("SI-IC-5", "Mission-supporting data with confirmed integrity", "%", (45, 46, 66, 81, 91, 100), False, None, 85),
        ("RE-S1-A1-1", "Mean time to detect suspect information", "min", (70, 69, 35, 15, 5, 0), False, None, 18),
        ("CS-S1-A1-2", "Number of corrupted-information checkpoints", "points", (1, 2, 3, 4, 6, 6), False, 1, 4),
        ("SI-IC-6", "Completeness of data validation", "level", (0, 0.25, 0.5, 0.75, 1, 1), False, 0.25, 1),
        ("RE-S1-A1-2", "Time to notify business functions", "min", (50, 49, 30, 15, 5, 0), False, None, 30),
    ],
    ("TR.S1.A1", "Analysis of mission flows for single points of failure", "AD", "Transform"): [
        ("M1", "Mission flows analyzed for SPOF", "%", (30, 31, 56, 76, 91, 100), False, None, 80),
        ("M2", "Analyzed flows without SPOF", "%", (25, 26, 46, 66, 86, 100), False, None, 60),
    ],
    ("TR.S2.A2", "Restriction of privileges", "AD", "Re-architect"): [
        ("M1", "Resources with privilege requirements analyzed", "%", (35, 36, 61, 76, 91, 100), False, None, 80),
        ("M2", "Problematic privilege assignments changed", "%", (30, 31, 51, 71, 86, 100), False, None, 75),
    ],
}

UN_S1_WEIGHTS = (0.25, 0.15, 0.25, 0.20, 0.05, 0.10)
SHARED_SOURCES = {"AM-DA-1": "AM-DA-1"}   # one physical measurement feeds two actions

STATES = {"E1": 0.0, "E2": -0.5, "E3": 0.5, "E4": -1.0, "E5": 1.0}
STATE_NAMES = {"E1": "Current state", "E2": "Degraded state", "E3": "Improved state",
               "E4": "Critical state", "E5": "Ideal state"}
EXPECTED_LEVELS = {"E1": 3, "E2": 2, "E3": 4, "E4": 1, "E5": 5}


def _sigma(xi) -> int:
    return 1 if xi[0] < xi[5] else -1


def bnk_pay(theta: float = 0.5, operator: str = "capped", **kw) -> Configuration:
    """Configuration of the bank payment processing center BNK_PAY."""
    actions = []
    for (acode, aname, goal, task), rows in _RAW.items():
        q = len(rows)
        ws = UN_S1_WEIGHTS if acode == "UN.S1.A1" else (1.0 / q,) * q
        metrics = tuple(
            Metric(code=c, name=n, unit=u, xi=tuple(float(v) for v in xi), sigma=_sigma(xi),
                   weight=float(w), core=core, step=step,
                   source=SHARED_SOURCES.get(c, f"{acode}.{c}"))
            for (c, n, u, xi, core, step, _), w in zip(rows, ws))
        actions.append(BasicAction(acode, aname, goal, task, metrics))
    return Configuration(scenario="BNK_PAY", threat="T1566 Phishing",
                         actions=tuple(actions), theta=theta, operator=operator, **kw)


def e1_values() -> dict[tuple[str, str], Optional[float]]:
    """Measurement sheet X of the current state E1 (None = not reported)."""
    return {(acode, row[0]): (None if row[6] is None else float(row[6]))
            for (acode, *_), rows in _RAW.items() for row in rows}


def round_to_step(x: float, step: Optional[float]) -> float:
    """Round a discrete metric to the nearest attainable value, ties to even."""
    if step is None:
        return x
    return float(np.round(x / step) * step)


def generate_state(cfg: Configuration, base: dict, t: float) -> dict:
    """State generator (12): u' = u + |t| (eta* - u), x' = sigma u'.

    t in [-1, 1]; t > 0 moves every observed value toward the ideal anchor,
    t < 0 toward the critical anchor. Discrete metrics are rounded.
    """
    if not -1.0 <= t <= 1.0:
        raise ValueError("t must lie in [-1, 1]")
    out = {}
    for a in cfg.actions:
        for m in a.metrics:
            x = base[(a.code, m.code)]
            if x is None:
                out[(a.code, m.code)] = None
                continue
            eta = m.anchors
            u = m.sigma * x
            target = eta[5] if t > 0 else eta[0]
            u2 = u + abs(t) * (target - u)
            out[(a.code, m.code)] = round_to_step(m.sigma * u2 + 0.0, m.step)
    return out


def five_states(cfg: Configuration, source: str = "table") -> dict[str, dict]:
    """Input states E1-E5.

    source="table" returns the values published in Table A1 (default, reproduces
    the manuscript); source="rule" regenerates E2-E5 from E1 by rule (12).
    """
    if source == "table":
        return table_a1()
    base = e1_values()
    return {e: (dict(base) if t == 0 else generate_state(cfg, base, t)) for e, t in STATES.items()}


# Reference values published in CRTM [37] for state E1 (Table 5): 15 values.
REFERENCE_E1 = {
    "actions": {"UN.S1.A1": 0.856, "UN.S2.A1": 0.670, "CN.S1.A1": 0.588, "CN.S2.A1": 0.599,
                "RE.S1.A2": 0.719, "TR.S1.A1": 0.682, "TR.S2.A2": 0.753},
    "enclosure": {"CN.S2.A1": (0.539, 0.639)},
    "goals_mean": {"ANT": 0.763, "WITH": 0.594, "REC": 0.719, "AD": 0.718},
    "goals_min": {"ANT": 0.670, "WITH": 0.588, "REC": 0.719, "AD": 0.682},
}


# Published Table A1, columns E2-E5, in the order of _RAW (n.r. = None).
_TABLE_A1 = """\
2 4 0 4|48.5 96 1 96|102 12.5 180 0|142 22.5 240 0|2 6 0 9|2 4 0 5
741600 352800 777600 0|2 4 0 4|55 90 30 100
255 105 300 0|31.5 9 45 0|62.5 92.5 40 100|50 85 30 100|37.5 12.5 50 0|55 20 70 0|57.5 87.5 40 100|65 27.5 75 0|62.5 87.5 50 100|2.1 5.5 0.2 7
255 105 300 0|16 3.5 25 0|60 90 40 100|55 87.5 35 100|32.5 12.5 40 0|55 20 70 0|64 91.5 45 100|25 7.5 35 0|- - - -|0.6 4 0.2 7
70 95 50 100|65 92.5 45 100|44 9 70 0|2 5 1 6|0.5 1 0 1|40 15 50 0
55 90 30 100|42.5 80 25 100
57.5 90 35 100|52.5 87.5 30 100"""


def table_a1() -> dict[str, dict]:
    """Input values of E1-E5 exactly as published in Table A1 of the manuscript."""
    states = {"E1": e1_values(), "E2": {}, "E3": {}, "E4": {}, "E5": {}}
    for ((acode, *_), rows), line in zip(_RAW.items(), _TABLE_A1.splitlines()):
        for row, cell in zip(rows, line.split("|")):
            for e, v in zip(("E2", "E3", "E4", "E5"), cell.split()):
                states[e][(acode, row[0])] = None if v == "-" else float(v)
    return states


def compare_rule_with_table(cfg: Configuration) -> list[dict]:
    """Differences between generator (12) and the published Table A1."""
    rule, tab = five_states(cfg, source="rule"), table_a1()
    diffs = []
    for e in ("E2", "E3", "E4", "E5"):
        for k, v in tab[e].items():
            r = rule[e][k]
            if (v is None) != (r is None) or (v is not None and abs(v - r) > 1e-9):
                diffs.append({"state": e, "action": k[0], "metric": k[1], "table": v, "rule": r})
    return diffs
