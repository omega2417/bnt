"""Model parameters for the evidence-bound action warrant (EBAW) simulation.

All values are illustrative design parameters for a synthetic workload.
Ledger confirmation latencies are parameterized from published Avalanche
figures: ~1 s acceptance / sub-second finality claimed by the vendor
documentation, and tens of seconds observed under load in the Diablo
benchmark (EuroSys 2023).  Time unit: seconds.
"""
from __future__ import annotations

import copy
import numpy as np

PREDICATES = ("F", "C", "L", "V", "D")  # freshness, confidence, ledger quorum, version, deadline
PRED_NAMES = {
    "F": "Freshness",
    "C": "Calibrated confidence",
    "L": "Ledger quorum",
    "V": "Policy version",
    "D": "Deadline budget",
}

# action class: selection probability, risk tier, freshness bound Phi (s), response
# deadline D (s, from observation), median execution time tau (s), state-drift
# time constant (s, chosen as 20*Phi so that P[drift by Phi] ~= 4.9 %)
ACTIONS = {
    "block_ip":        dict(p=0.22, tier="low",      Phi=600.0, D=900.0, tau=2.0),
    "kill_process":    dict(p=0.18, tier="medium",   Phi=120.0, D=180.0, tau=2.0),
    "quarantine_file": dict(p=0.15, tier="medium",   Phi=300.0, D=600.0, tau=4.0),
    "revoke_sessions": dict(p=0.12, tier="medium",   Phi=600.0, D=900.0, tau=5.0),
    "disable_account": dict(p=0.13, tier="high",     Phi=300.0, D=600.0, tau=4.0),
    "isolate_host":    dict(p=0.15, tier="high",     Phi=180.0, D=300.0, tau=8.0),
    "isolate_server":  dict(p=0.05, tier="critical", Phi=120.0, D=300.0, tau=15.0),
}
for _a in ACTIONS.values():
    _a["drift"] = 20.0 * _a["Phi"]
ACTION_NAMES = list(ACTIONS)
ACTION_P = np.array([ACTIONS[a]["p"] for a in ACTION_NAMES])
ACTION_P = ACTION_P / ACTION_P.sum()

# risk tier -> (theta_auto, theta_observe) on the conservative calibrated confidence
TIERS = {"low": (0.80, 0.50), "medium": (0.88, 0.60), "high": (0.93, 0.70), "critical": (0.97, 0.80)}

TAU_SIGMA = 0.4          # log-sd of execution time
T_WAIT = 30.0            # max wait for ledger confirmation (s)
Z_LCB = 1.645            # one-sided 95 % Wilson lower bound
N_BINS = 25              # equal-mass calibration bins
N_CAL = 40000            # calibration sample size
COST_UNSAFE, COST_MISS, COST_ESC = 10.0, 5.0, 1.0

BASE = dict(
    rate_per_h=45.0, horizon=8 * 3600.0, p_mal=0.70,
    mal_beta=(6.0, 1.5), ben_beta=(1.5, 4.0),
    ing_median=8.0, ing_sigma=0.6, stale_p=0.0, stale_lo=60.0, stale_hi=400.0,
    agent_median=12.0, agent_sigma=0.5,
    ds=0.2, lc_median=1.0, lc_sigma=0.35, lc_delay_p=0.0, lc_delay_lo=15.0, lc_delay_hi=60.0,
    lc_stall_p=0.0, lc_stall_lo=120.0, lc_stall_hi=600.0,
    dq_median=0.08, dg_median=0.035, dc_median=0.02, lat_sigma=0.4,
    prep_median=25.0, prep_sigma=0.8, n_orch=3,
    analyst_median=240.0, analyst_sigma=0.6, n_analyst=2, analyst_acc=0.95,
    refresh_median=10.0, refresh_sigma=0.5,
    pol_rate_rel_per_h=0.1, p_forbid=0.5,
    ret_p_benign=0.30, ret_mean=300.0,
    adv_halluc=0.01, adv_inject=0.005, adv_tamper=0.003,
    surge=(), surge_mult=8.0,
)

SCENARIOS = {
    "S0": ("Nominal operation", {}),
    "S1": ("Delayed confirmation", dict(lc_delay_p=0.30, lc_stall_p=0.03)),
    "S2": ("Stale telemetry", dict(stale_p=0.25)),
    "S3": ("Policy churn", dict(pol_rate_rel_per_h=3.0)),
    "S4": ("Evidence retraction", dict(ret_p_benign=0.85, ret_mean=30.0)),
    "S5": ("Adversarial proposals", dict(adv_halluc=0.10, adv_inject=0.06, adv_tamper=0.04)),
    "S6": ("Alert surge", dict(surge=((2 * 3600.0, 2 * 3600.0 + 1200.0), (5 * 3600.0, 5 * 3600.0 + 1200.0)))),
    "S7": ("Combined stress", dict(lc_delay_p=0.15, lc_stall_p=0.015, stale_p=0.12, pol_rate_rel_per_h=1.5,
                                   ret_p_benign=0.60, ret_mean=60.0, adv_halluc=0.05, adv_inject=0.03,
                                   adv_tamper=0.02, surge=((3 * 3600.0, 3 * 3600.0 + 1200.0),))),
}


def scenario_params(key: str) -> dict:
    p = copy.deepcopy(BASE)
    p.update(SCENARIOS[key][1])
    return p


class Calibrator:
    """Equal-mass histogram binning with one-sided Wilson lower bounds and a conservative
    monotone envelope: c(s) = conservative estimate of P(malicious | score s)."""

    def __init__(self, params: dict, seed: int = 42):
        rng = np.random.default_rng(seed)
        y = (rng.random(N_CAL) < params["p_mal"]).astype(int)
        s = np.where(y == 1, rng.beta(*params["mal_beta"], N_CAL), rng.beta(*params["ben_beta"], N_CAL))
        edges = np.quantile(s, np.linspace(0, 1, N_BINS + 1))
        edges[0], edges[-1] = 0.0, 1.0
        idx = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, N_BINS - 1)
        lcb, phat, nb = [], [], []
        for b in range(N_BINS):
            m = idx == b
            n, k = int(m.sum()), int(y[m].sum())
            p = k / n
            lcb.append(wilson_lcb(k, n, Z_LCB))
            phat.append(p)
            nb.append(n)
        self.edges = edges
        # conservative monotonisation: the lower envelope of the bin bounds from the top,
        # g(b) = min_{b' >= b} lcb_{b'}, is non-decreasing and never exceeds a bin's own bound
        self.lcb = np.minimum.accumulate(np.array(lcb)[::-1])[::-1]
        self.phat = np.array(phat)
        self.n = np.array(nb)

    def __call__(self, s):
        idx = np.clip(np.searchsorted(self.edges, s, side="right") - 1, 0, N_BINS - 1)
        return self.lcb[idx]


def wilson_lcb(k: int, n: int, z: float) -> float:
    if n == 0:
        return 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half)


def wilson_ci(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))
