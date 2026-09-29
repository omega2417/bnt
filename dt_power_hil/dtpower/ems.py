"""EMS policies C0, C1, C2 and the information bound C_oracle (section 11).

C2 is a *forecast-based control rule*, not MPC and not RL (section 11.3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Decision:
    aux_on: bool
    reason: str
    predicted_min_soc: float | None = None
    predicted_min_soc_off: float | None = None


@dataclass
class PolicyBase:
    name: str
    cfg: dict
    aux_state: bool = False
    t_last_switch: float = -1e9
    history: list = field(default_factory=list)

    def _dwell_ok(self, t: float) -> bool:
        return t - self.t_last_switch >= self.cfg.get("minimum_dwell_s", 0)

    def _commit(self, t: float, d: Decision) -> Decision:
        if d.aux_on != self.aux_state:
            self.t_last_switch = t
        self.aux_state = d.aux_on
        self.history.append((t, d))
        return d


class C0(PolicyBase):
    def decide(self, t, soc, sched_now, **_):
        return self._commit(t, Decision(bool(sched_now), "schedule"))


class C1(PolicyBase):
    def decide(self, t, soc, sched_now, **_):
        c = self.cfg
        if not sched_now:
            return self._commit(t, Decision(False, "schedule_off"))
        if self.aux_state and soc <= c["aux_off_soc"]:
            return self._commit(t, Decision(False, "soc_below_off"))
        if not self.aux_state:
            if soc >= c["aux_on_soc"] and self._dwell_ok(t):
                return self._commit(t, Decision(True, "soc_above_on"))
            return self._commit(t, Decision(False, "hold_off"))
        return self._commit(t, Decision(True, "hold_on"))


class C2(PolicyBase):
    """Forecast-based rule: simulate horizon with/without aux, keep reserve."""

    def decide(self, t, soc, sched_now, *, twin, gen_fc, load_crit_bus_fc, aux_sched_bus_fc, **_):
        c = self.cfg
        if not sched_now:
            return self._commit(t, Decision(False, "schedule_off"))
        step = c["step_s"]
        n = int(c["horizon_s"] // step)
        with_aux = twin.predict_trajectory(soc, gen_fc[:n], load_crit_bus_fc[:n] + aux_sched_bus_fc[:n], step)
        no_aux = twin.predict_trajectory(soc, gen_fc[:n], load_crit_bus_fc[:n], step)
        mn, mn_off = float(np.min(with_aux)), float(np.min(no_aux))
        if self.aux_state:
            if mn < c["reserve_soc"]:
                return self._commit(t, Decision(False, "forecast_min_below_reserve", mn, mn_off))
            return self._commit(t, Decision(True, "forecast_ok", mn, mn_off))
        if mn >= c["return_pred_soc"] and soc >= c["return_now_soc"] and self._dwell_ok(t):
            return self._commit(t, Decision(True, "forecast_return", mn, mn_off))
        return self._commit(t, Decision(False, "forecast_hold_off", mn, mn_off))


def make_policy(name: str, pcfg: dict) -> PolicyBase:
    if name == "C0":
        return C0(name, pcfg["C0"])
    if name == "C1":
        return C1(name, pcfg["C1"])
    if name in ("C2", "C_oracle"):
        return C2(name, pcfg["C2"])
    raise ValueError(name)
