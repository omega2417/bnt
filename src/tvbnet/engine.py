"""Threat-vulnerability-barrier risk engine and configuration-selection methods.

Equations (manuscript numbering):
  (1) V_a   = M * r_a * (w_T*T_a + w_E*E_a + w_S*S_a)                 information value
  (2) p_ta  = g_ta * [1 - prod_{v in V(a,c_t)} (1 - p_v)]               success probability
  (3) m_bta = e_b * alpha(l_b, c_t) * s_ba * [not (l_b = L1 and t internal)]
  (4) pi_ta(x) = prod_b (1 - m_bta x_b)                               multilayer pass probability
  (5) R(x)  = sum_t sum_a lambda_t p_ta I_ta pi_ta(x),  I_ta = k_I * s_t * V_a
  (6) C(x)  = sum_b c_b x_b ;   x* = argmin R(x) s.t. C(x) <= B,  B = beta * sum_b c_b
  (7) kappa_t(x) = 1 - sum_a W_ta pi_ta / sum_a W_ta                  weighted threat coverage
  (8) CH(x): share of exposed pairs with a selected barrier m_bta >= theta; coverage depth
  (9) ROSI = (R(0) - R(x) - C(x)) / C(x)
 (10) reliability-perturbed estimates (generate.py)
 (11) regret = [R(x_hat) - R(x*)] / R(0)
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from .generate import AFFINITY, CLASSES


@lru_cache(maxsize=None)
def subset_matrix(m: int) -> np.ndarray:
    ints = np.arange(2 ** m, dtype=np.int64)
    return ((ints[:, None] >> np.arange(m)) & 1).astype(np.float64)


class Instance:
    """Numerical arrays for one scenario. basis='true' or 'est'."""

    def __init__(self, sc: dict, design: dict, cfg: dict, basis: str = "true"):
        self.basis = basis
        assets, threats, barriers, vulns = sc["assets"], sc["threats"], sc["barriers"], sc["vulnerabilities"]
        A, T, m = len(assets), len(threats), len(barriers)
        self.A, self.T, self.m = A, T, m
        aidx = {a["asset_id"]: i for i, a in enumerate(assets)}
        V = np.array([a["info_value_kcu"] for a in assets])
        hops = np.array([a["hops"] for a in assets], float)
        cls = np.array([CLASSES.index(t["threat_class"]) for t in threats])
        self.cls = cls
        internal = np.array([t["origin"] == "internal" for t in threats])
        lam = np.array([t["rate_est" if basis == "est" else "rate_per_year"] for t in threats])
        sev = np.array([t["severity_est" if basis == "est" else "severity"] for t in threats])
        # (2) success probability
        surv = np.ones((T, A))
        for v in vulns:
            a = aidx[v["asset_id"]]
            for t in range(T):
                if v["class_mask"][cls[t]] == "1":
                    surv[t, a] *= 1.0 - v["exploitability"]
        g = np.where(internal[:, None], 1.0, np.exp(-cfg["hop_attenuation"] * (hops[None, :] - 1)))
        self.p = g * (1.0 - surv)
        self.I = design["impact_multiplier"] * sev[:, None] * V[None, :]
        self.W = lam[:, None] * self.p * self.I                       # unprotected annual loss per pair
        e = np.array([b["effectiveness_est" if basis == "est" else "effectiveness"] for b in barriers])
        self.cost = np.array([b["cost_est" if basis == "est" else "annual_cost_kcu"] for b in barriers])
        self.cost_true = np.array([b["annual_cost_kcu"] for b in barriers])
        self.layer = np.array([b["layer_index"] for b in barriers])
        scope = np.array([[c == "1" for c in b["scope_mask"]] for b in barriers], float)
        aff = AFFINITY[self.layer - 1][:, cls]                        # m x T
        l1_block = (self.layer[:, None] == 1) & internal[None, :]
        aff = np.where(l1_block, 0.0, aff)
        self.M = e[:, None, None] * aff[:, :, None] * scope[:, None, :]   # (3)  m x T x A
        self.logq = np.log1p(-np.clip(self.M, 0, 1 - 1e-12)).reshape(m, T * A)
        self.Wf = self.W.reshape(-1)
        self.budget = design["budget_fraction"] * self.cost_true.sum()
        self.R0 = float(self.W.sum())

    # (4)-(5)
    def risk(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X).astype(float)
        return np.exp(X @ self.logq) @ self.Wf

    def pass_prob(self, x: np.ndarray) -> np.ndarray:
        return np.exp(np.asarray(x, float) @ self.logq).reshape(self.T, self.A)

    def indicators(self, x: np.ndarray, theta: float) -> dict:
        x = np.asarray(x, float)
        pi = self.pass_prob(x)
        R = float((self.W * pi).sum())
        exposed = self.W > 0
        wsum = self.W.sum(1)
        kappa = np.where(wsum > 0, 1 - (self.W * pi).sum(1) / np.where(wsum > 0, wsum, 1), np.nan)   # (7)
        sel = x > 0.5
        strong = (self.M[sel] >= theta) if sel.any() else np.zeros((0, self.T, self.A), bool)
        covered = strong.any(0) if sel.any() else np.zeros((self.T, self.A), bool)
        layers_sel = self.layer[sel]
        depth = np.zeros((self.T, self.A))
        for L in np.unique(layers_sel):
            depth += strong[layers_sel == L].any(0)
        C = float((self.cost_true * x).sum())
        return {
            "residual_risk_kcu": R,
            "cost_kcu": C,
            "risk_reduction_kcu": self.R0 - R,
            "rosi": (self.R0 - R - C) / C if C > 0 else np.nan,                                     # (9)
            "ch_coverage": float(covered[exposed].mean()) if exposed.any() else np.nan,
            "mean_coverage_depth": float(depth[exposed].mean()) if exposed.any() else np.nan,
            "mean_threat_coverage": float(np.nanmean(kappa)),
            "min_threat_coverage": float(np.nanmin(kappa)),
            "n_selected": int(sel.sum()),
            "n_layers_used": int(len(np.unique(layers_sel))),
        }

    def layer_cascade(self, x: np.ndarray) -> np.ndarray:
        """Residual annual loss by threat class after applying selected barriers of layers 1..k (rows k=0..5)."""
        x = np.asarray(x, float)
        out = np.zeros((6, len(CLASSES)))
        for k in range(6):
            loss_t = (self.W * self.pass_prob(x * (self.layer <= k))).sum(1)
            np.add.at(out[k], self.cls, loss_t)
        return out


def mask_to_bits(mask: int, m: int) -> str:
    return "".join("1" if (mask >> i) & 1 else "0" for i in range(m))


def bits_to_vec(bits: str) -> np.ndarray:
    return np.array([c == "1" for c in bits], float)


def enumerate_all(inst: Instance):
    X = subset_matrix(inst.m)
    return inst.risk(X), X @ inst.cost


def exact(R: np.ndarray, C: np.ndarray, B: float) -> int:
    feas = np.flatnonzero(C <= B + 1e-12)
    Rf = R[feas]
    best = feas[np.flatnonzero(Rf <= Rf.min() * (1 + 1e-12))]
    return int(best[np.argmin(C[best])])


def frontier(R: np.ndarray, C: np.ndarray) -> np.ndarray:
    order = np.lexsort((R, C))
    keep, best = [], np.inf
    for i in order:
        if R[i] < best * (1 - 1e-12):
            keep.append(i); best = R[i]
    return np.array(keep, dtype=np.int64)


def greedy(R: np.ndarray, cost: np.ndarray, B: float) -> int:
    mask, spent, m = 0, 0.0, len(cost)
    while True:
        best, best_ratio = None, 0.0
        for b in range(m):
            if (mask >> b) & 1 or spent + cost[b] > B + 1e-12:
                continue
            gain = R[mask] - R[mask | (1 << b)]
            ratio = gain / cost[b]
            if ratio > best_ratio + 1e-15:
                best, best_ratio = b, ratio
        if best is None:
            return mask
        mask |= 1 << best; spent += cost[best]


def layer_uniform(layer: np.ndarray, cost: np.ndarray, B: float) -> int:
    mask, spent = 0, 0.0
    for L in sorted(set(layer.tolist())):
        idx = np.flatnonzero(layer == L)
        b = idx[np.argmin(cost[idx])]
        if spent + cost[b] <= B + 1e-12:
            mask |= 1 << int(b); spent += cost[b]
    return mask


def by_order(order, cost: np.ndarray, B: float) -> int:
    mask, spent = 0, 0.0
    for b in order:
        if spent + cost[b] <= B + 1e-12:
            mask |= 1 << int(b); spent += cost[b]
    return mask
