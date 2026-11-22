"""Digital twin of the processing center BNK_PAY that emits metric telemetry.

The twin is a SYNTHETIC simulator (not field data). Each metric has a latent
position p in [0, 1] between its critical and ideal anchors that follows a
mean-reverting process around a target; scheduled events move the targets:

* phishing incident      -- damage-assessment and verification times degrade;
* TI provider outage     -- the number of TI sources drops to zero (core veto);
* improvement programme  -- targets move toward the ideal anchors.

On top of the latent state the sensors produce missing values, spikes and
stuck readings; the ground-truth fault labels are kept for evaluating the
data-quality agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..fast import BatchEvaluator
from ..model import Configuration
from ..scenarios import e1_values


@dataclass
class Event:
    name: str
    start: int
    end: int
    targets: dict            # key or prefix -> new target position (or delta if 'delta')
    mode: str = "set"        # set | delta


def default_events() -> list[Event]:
    return [
        Event("Phishing incident", 60, 85, {
            ("CN.S1.A1", "AM-DA-1"): 0.05, ("CN.S2.A1", "AM-DA-1"): 0.05,
            ("CN.S1.A1", "SI-IC-1"): 0.25, ("CN.S2.A1", "SI-IC-1"): 0.3,
            ("CN.S1.A1", "SI-BV-1"): 0.25, ("RE.S1.A2", "RE-S1-A1-1"): 0.3,
            ("RE.S1.A2", "RE-S1-A1-2"): 0.2}),
        Event("TI provider outage", 115, 128, {("UN.S1.A1", "M1"): 0.0, ("UN.S1.A1", "M2"): 0.2}),
        Event("Improvement programme", 150, 10_000, {"*": 0.35}, mode="delta"),
    ]


@dataclass
class DigitalTwin:
    cfg: Configuration
    seed: int = 0
    events: list = field(default_factory=default_events)
    theta_mr: float = 0.15          # mean-reversion speed
    noise: float = 0.015
    p_missing: float = 0.02
    p_spike: float = 0.006
    p_stuck_start: float = 0.002
    stuck_len: int = 12

    def __post_init__(self):
        self.be = BatchEvaluator(self.cfg)
        X0, m0 = self.be.to_matrix([e1_values()])
        self.p0 = self.be.position(np.where(m0, X0, 0.0))[0]
        self.never = ~m0[0]                     # metrics never reported in the scenario
        self.rng = np.random.default_rng(self.seed)
        self.p = self.p0.copy()
        self.t = 0
        self.stuck = np.zeros(self.be.d, int)
        self.stuck_val = np.zeros(self.be.d)
        self.keys = self.be.keys
        self._shared = [(i, j) for i, ki in enumerate(self.keys) for j, kj in enumerate(self.keys)
                        if i < j and ki[1] == kj[1] == "AM-DA-1"]

    def target(self, t: int) -> np.ndarray:
        tgt = self.p0.copy()
        for ev in self.events:
            if ev.start <= t < ev.end:
                for k, v in ev.targets.items():
                    if k == "*":
                        sel = np.ones(self.be.d, bool)
                        tgt[sel] = np.clip(tgt[sel] + v * (1 - tgt[sel]), 0, 1) if ev.mode == "delta" else v
                    else:
                        j = self.keys.index(k)
                        tgt[j] = np.clip(tgt[j] + v, 0, 1) if ev.mode == "delta" else v
        return tgt

    def step(self) -> dict:
        """Advance one tick; returns sheet, latent sheet and fault labels."""
        tgt = self.target(self.t)
        fast = np.array([abs(tgt[j] - self.p[j]) > 0.3 for j in range(self.be.d)])
        k = np.where(fast, 0.5, self.theta_mr)
        self.p = np.clip(self.p + k * (tgt - self.p) + self.rng.normal(0, self.noise, self.be.d), 0, 1)
        for i, j in self._shared:               # one physical measurement feeds two actions
            self.p[j] = self.p[i]
        true_x = self.be.from_position(self.p[None, :])[0]
        obs_p = self.p.copy()
        fault = np.zeros(self.be.d, int)        # 0 ok, 1 missing, 2 spike, 3 stuck
        # stuck sensors
        start = (self.rng.uniform(size=self.be.d) < self.p_stuck_start) & (self.stuck == 0)
        self.stuck_val[start] = obs_p[start]
        self.stuck[start] = self.stuck_len
        st = self.stuck > 0
        obs_p[st] = self.stuck_val[st]
        fault[st & (np.abs(self.stuck_val - self.p) > 0.08)] = 3
        self.stuck[st] -= 1
        # spikes (sensor glitches)
        sp = self.rng.uniform(size=self.be.d) < self.p_spike
        obs_p[sp] = np.where(self.p[sp] > 0.5, self.rng.uniform(0, 0.15, sp.sum()),
                             self.rng.uniform(0.85, 1.0, sp.sum()))
        fault[sp] = 2
        x = self.be.from_position(obs_p[None, :])[0]
        miss = (self.rng.uniform(size=self.be.d) < self.p_missing) & ~self.be.core
        miss |= self.never
        fault[miss & ~self.never] = 1
        sheet = {kk: (None if miss[j] else float(x[j])) for j, kk in enumerate(self.keys)}
        truth = {kk: (None if self.never[j] else float(true_x[j])) for j, kk in enumerate(self.keys)}
        out = {"t": self.t, "sheet": sheet, "truth": truth, "fault": fault,
               "events": [e.name for e in self.events if e.start <= self.t < e.end]}
        self.t += 1
        return out

    def run(self, n: int) -> list[dict]:
        return [self.step() for _ in range(n)]
