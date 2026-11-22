"""Benchmark tasks on the EBAW-SOC-Synth dataset.

T1  calibration: fit the conservative calibration map g (Eqs. 3-4) on the train split and
    evaluate it on the test split (ECE, Brier score, conservativeness);
T2  threshold selection: choose the AUTO threshold of every risk tier on the validation split
    (offline cost proxy) and compare it with the thresholds of the article;
T3  admission policies: unsafe-execution rate, contract-violation rate, deadline-miss rate,
    escalation rate and expected cost J of the six policies on the test split, with Wilson
    intervals, adversarial executions with exact zero-event bounds, and the sample sizes of
    Section 6.3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import BASE, COST_ESC, COST_MISS, COST_UNSAFE, TIERS, Z_LCB, Calibrator, wilson_ci, wilson_lcb
from .stats import (conservativeness, expected_calibration_error, n_two_proportions, rule_of_three_n,
                    zero_event_upper)

ORDER = ["AD", "CO", "RO", "GN", "EB", "ET"]


class EmpiricalCalibrator:
    """Equal-mass binning with one-sided Wilson lower bounds and the conservative monotone
    envelope g(b) = min_{b' >= b} lcb_{b'} (Eqs. 3-4), fitted on labeled scores."""

    def __init__(self, s, y, n_bins: int = 12, z: float = Z_LCB):
        s, y = np.asarray(s, float), np.asarray(y, int)
        edges = np.quantile(s, np.linspace(0, 1, n_bins + 1))
        edges[0], edges[-1] = 0.0, 1.0
        idx = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, n_bins - 1)
        lcb, phat, nb = [], [], []
        for b in range(n_bins):
            m = idx == b
            n, k = int(m.sum()), int(y[m].sum())
            lcb.append(wilson_lcb(k, n, z))
            phat.append(k / n if n else 0.0)
            nb.append(n)
        self.edges, self.n_bins = edges, n_bins
        self.lcb = np.minimum.accumulate(np.array(lcb)[::-1])[::-1]
        self.phat, self.n = np.array(phat), np.array(nb)

    def __call__(self, s):
        idx = np.clip(np.searchsorted(self.edges, s, side="right") - 1, 0, self.n_bins - 1)
        return self.lcb[idx]


def labeled_scores(D: dict, split: str):
    """Scores and labels of genuine proposals whose episode belongs to ``split``."""
    P = D["proposals"].merge(D["episodes"][["episode_id", "split"]], on="episode_id")
    P = P[(P.kind == "genuine") & (P.split == split)]
    O = D["observations"].set_index("evidence_id")
    s = O.loc[P.evidence_refs, "score"].to_numpy()
    return s, P.y_malicious.to_numpy().astype(int), P


def task_calibration(D: dict, n_bins: int = 12) -> dict:
    s_tr, y_tr, _ = labeled_scores(D, "train")
    s_te, y_te, _ = labeled_scores(D, "test")
    cal = EmpiricalCalibrator(s_tr, y_tr, n_bins)
    ref = Calibrator(BASE, 42)
    out = dict(n_train=int(len(s_tr)), n_test=int(len(s_te)), prevalence_train=float(y_tr.mean()),
               prevalence_test=float(y_te.mean()))
    for name, g in (("fitted", cal), ("article", ref)):
        c = g(s_te)
        out[name] = dict(ECE=expected_calibration_error(c, y_te), Brier=float(np.mean((c - y_te) ** 2)),
                         conservative_bins=conservativeness(c, y_te),
                         overconfident_mass=_overconfident_mass(c, y_te))
    out["map"] = pd.DataFrame(dict(lo=cal.edges[:-1], hi=cal.edges[1:], n=cal.n, phat=cal.phat, g=cal.lcb))
    out["_cal"] = cal
    return out


def _overconfident_mass(c, y, n_bins=15):
    """Share of test samples in bins whose mean confidence exceeds the empirical precision by
    more than its 95 % Wilson half-width (i.e. significantly overconfident)."""
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(c, edges) - 1, 0, n_bins - 1)
    bad = 0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            lo, hi = wilson_ci(int(y[m].sum()), int(m.sum()))
            if c[m].mean() > hi:
                bad += int(m.sum())
    return bad / len(c)


def task_thresholds(D: dict, cal, grid=None, c_u=COST_UNSAFE, c_e=COST_ESC) -> pd.DataFrame:
    """Offline proxy on the validation split: a proposal with g >= theta executes
    autonomously (cost c_U if the target is benign), otherwise it is escalated (cost c_E).
    The selected theta minimizes the mean cost per proposal of the tier."""
    grid = np.round(np.arange(0.50, 1.00, 0.01), 2) if grid is None else grid
    s, y, P = labeled_scores(D, "val")
    g = cal(s)
    rows = []
    for tier, (ta, _) in TIERS.items():
        m = (P.tier == tier).to_numpy()
        if not m.any():
            continue
        cost = [(c_u * np.sum((g[m] >= th) & (y[m] == 0)) + c_e * np.sum(g[m] < th)) / m.sum() for th in grid]
        k = int(np.argmin(cost))
        prec = y[m][g[m] >= grid[k]].mean() if np.any(g[m] >= grid[k]) else float("nan")
        rows.append(dict(tier=tier, n_val=int(m.sum()), theta_article=ta, theta_selected=float(grid[k]),
                         cost_selected=float(cost[k]), cost_at_article=float(cost[int(np.argmin(abs(grid - ta)))]),
                         precision_selected=float(prec)))
    return pd.DataFrame(rows)


def task_policies(D: dict, split: str = "test") -> dict:
    P = D["proposals"].merge(D["episodes"][["episode_id", "split"]], on="episode_id")
    if split != "all":
        P = P[P.split == split]
    PO = D["policy_outcomes"].merge(P[["proposal_id", "kind", "y_malicious", "scenario_id"]], on="proposal_id")
    rows, per_sc = [], []
    for pol in ORDER:
        x = PO[PO.policy == pol]
        n = len(x)
        mal = x[(x.kind == "genuine") & (x.y_malicious == 1)]
        auto = x[x.executed & ~x.manual]
        adv = x[x.kind != "genuine"]
        unsafe, miss, esc = int(x.unsafe.sum()), int((~mal.deadline_met.astype(bool)).sum()), int(x.escalated.sum())
        lo, hi = wilson_ci(unsafe, n)
        a_exec = int(adv.executed.sum())
        rows.append(dict(policy=pol, n=n, UER=1000 * unsafe / n, UER_lo=1000 * lo, UER_hi=1000 * hi,
                         CVR=100 * auto.violation.mean() if len(auto) else 0.0, n_auto=len(auto),
                         DMR=100 * miss / max(1, len(mal)), ESC=100 * esc / n,
                         adv_exec=a_exec, n_adv=len(adv),
                         adv_upper95=(100 * zero_event_upper(len(adv)) if a_exec == 0 else
                                      100 * wilson_ci(a_exec, len(adv))[1]),
                         J=(COST_UNSAFE * unsafe + COST_MISS * miss + COST_ESC * esc) / n))
        for sc, y in x.groupby("scenario_id"):
            m = y[(y.kind == "genuine") & (y.y_malicious == 1)]
            per_sc.append(dict(scenario=sc, policy=pol, J=(COST_UNSAFE * y.unsafe.sum() + COST_MISS *
                                                           (~m.deadline_met.astype(bool)).sum() +
                                                           COST_ESC * y.escalated.sum()) / len(y)))
    tab = pd.DataFrame(rows).set_index("policy")
    Jsc = pd.DataFrame(per_sc).pivot(index="scenario", columns="policy", values="J")[ORDER]
    p1, p2 = float(tab.loc["CO", "UER"]) / 1000, float(tab.loc["EB", "UER"]) / 1000
    plan = dict(p_CO=p1, p_EB=p2, n_per_policy=n_two_proportions(p1, p2) if p1 != p2 else None,
                n_article=n_two_proportions(0.053, 0.015), n_adv_rule_of_three=rule_of_three_n(0.01),
                n_adv_available=int(tab.loc["EB", "n_adv"]))
    return dict(table=tab, J_by_scenario=Jsc, planning=plan)
