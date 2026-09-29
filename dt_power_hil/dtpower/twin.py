"""Digital twin: telemetry validation, SOC estimation (prior/posterior), energy
bookkeeping and short-horizon prediction (sections 9.2–9.6, 15.2–15.3).

The twin estimates state from channel M1 only. The reference SOC is computed
elsewhere (reference.py) from the independent REF channel (section 8.3).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .battery import docv_dz, ocv_pack

REQUIRED = ("seq", "v_batt_v", "i_batt_a", "p_gen_bus_w", "p_crit_bus_w", "p_aux_bus_w", "temp_batt_c")


@dataclass
class DataValidator:
    v_range: tuple = (8.0, 16.0)
    i_range: tuple = (-55.0, 55.0)
    stuck_n: int = 8
    residual_w: float = 3.0
    residual_n: int = 5
    _last_i: float | None = None
    _same: int = 0
    _res_bad: int = 0

    def check(self, m: dict, p_other_model_w: float = 0.35) -> tuple[bool, str]:
        for k in REQUIRED:
            if m.get(k) is None:
                return False, f"missing:{k}"
        if not (self.v_range[0] <= m["v_batt_v"] <= self.v_range[1]):
            return False, "impossible_voltage"
        if not (self.i_range[0] <= m["i_batt_a"] <= self.i_range[1]):
            return False, "impossible_current"
        if self._last_i is not None and m["i_batt_a"] == self._last_i:
            self._same += 1
        else:
            self._same = 0
        self._last_i = m["i_batt_a"]
        if self._same >= self.stuck_n:
            return False, "stuck_value"
        # bus balance residual r_P (9.2), battery power referred to the bus
        r = m["p_gen_bus_w"] + m["v_batt_v"] * m["i_batt_a"] - m["p_crit_bus_w"] - m["p_aux_bus_w"] - p_other_model_w
        self._res_bad = self._res_bad + 1 if abs(r) > self.residual_w else 0
        if self._res_bad >= self.residual_n:
            return False, "balance_residual"
        return True, "ok"


@dataclass
class Twin:
    q_model_ah: float
    eta_q_model: float
    r0_model: float
    z_post: float
    p_var: float = 1e-4
    q_proc: float = 2e-9
    r_meas: float = 0.03 ** 2
    tau_p_s: float = 200.0
    r1_model: float = 0.010
    v_p: float = 0.0
    last_i: float = 0.0
    valid_frac: list = field(default_factory=lambda: [0, 0])
    validator: DataValidator = field(default_factory=DataValidator)
    e_dis_wh: float = 0.0
    e_ch_wh: float = 0.0

    def _coulomb(self, z: float, i: float, dt: float) -> float:
        q = self.q_model_ah * 3600.0
        return z - i * dt / q if i >= 0 else z + self.eta_q_model * (-i) * dt / q

    def prior(self, dt: float) -> float:
        """Prediction before the new telemetry: last known current held (ZOH)."""
        return self._coulomb(self.z_post, self.last_i, dt)

    def update(self, m: dict, dt: float) -> dict:
        z_prior = self.prior(dt)
        ok, why = self.validator.check(m)
        self.valid_frac[1] += 1
        if not ok:
            # invalid sample: propagate the prior, do not correct (15.3)
            self.z_post = z_prior
            self.p_var += self.q_proc * dt
            return {"soc_prior": z_prior, "soc_posterior": self.z_post, "valid": False, "reason": why}
        self.valid_frac[0] += 1
        i, v = m["i_batt_a"], m["v_batt_v"]
        # time update with the measured mean current of the interval
        z = self._coulomb(self.z_post, i, dt)
        a = math.exp(-dt / self.tau_p_s)
        self.v_p = a * self.v_p + self.r1_model * (1 - a) * i
        p = self.p_var + self.q_proc * dt
        # EKF voltage correction; the LiFePO4 plateau makes H small -> weak correction
        h = docv_dz(z)
        v_hat = ocv_pack(z) - i * self.r0_model - self.v_p
        s = h * p * h + self.r_meas
        k = p * h / s
        z = min(1.0, max(0.0, z + k * (v - v_hat)))
        self.p_var = (1 - k * h) * p
        self.z_post, self.last_i = z, i
        pb = v * i * dt / 3600.0
        if pb > 0:
            self.e_dis_wh += pb
        else:
            self.e_ch_wh += -pb
        return {"soc_prior": z_prior, "soc_posterior": z, "valid": True, "reason": "ok", "soc_sd": math.sqrt(self.p_var)}

    def predict_trajectory(self, z0: float, p_gen_w, p_load_bus_w, step_s: float, v_nom: float = 13.1):
        """Open-loop SOC prediction for EMS (energy form, bus-referred powers)."""
        z, traj = z0, []
        for g, d in zip(p_gen_w, p_load_bus_w):
            i = (d - g) / v_nom
            if i < 0 and z >= 0.999:
                i = 0.0
            z = self._coulomb(z, i, step_s)
            traj.append(min(1.0, max(0.0, z)))
        return traj
