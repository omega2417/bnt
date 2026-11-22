"""Vectorised evaluator of Stages 3-6 for many input states at once.

Used to generate training data for the neural agents, for sweeps and for
what-if search. It is tested to agree with `system.assess` to 1e-12.
"""
from __future__ import annotations

import numpy as np

from .model import Configuration


class BatchEvaluator:
    def __init__(self, cfg: Configuration):
        self.cfg = cfg
        self.keys = cfg.keys()
        self.d = len(self.keys)
        y = np.asarray(cfg.breakpoints, float)
        self.y = y
        self.eta = np.array([m.anchors for a in cfg.actions for m in a.metrics], float)
        self.sigma = np.array([m.sigma for a in cfg.actions for m in a.metrics], float)
        self.xi = np.array([m.xi for a in cfg.actions for m in a.metrics], float)
        self.w = np.array([m.weight for a in cfg.actions for m in a.metrics], float)
        self.core = np.array([m.core for a in cfg.actions for m in a.metrics], bool)
        self.step = [m.step for a in cfg.actions for m in a.metrics]
        self.action_of = np.array([i for i, a in enumerate(cfg.actions) for _ in a.metrics])
        self.goal_of_action = [a.goal for a in cfg.actions]

    # ---------------------------------------------------------------- encoding
    def to_matrix(self, sheets: list[dict]) -> tuple[np.ndarray, np.ndarray]:
        X = np.zeros((len(sheets), self.d))
        mask = np.ones((len(sheets), self.d), bool)
        for i, s in enumerate(sheets):
            for j, k in enumerate(self.keys):
                v = s.get(k)
                if v is None:
                    mask[i, j] = False
                else:
                    X[i, j] = v
        return X, mask

    def to_sheet(self, x: np.ndarray, mask: np.ndarray | None = None) -> dict:
        return {k: (None if mask is not None and not mask[j] else float(x[j]))
                for j, k in enumerate(self.keys)}

    def position(self, X: np.ndarray) -> np.ndarray:
        """Linear position of a value between its critical (0) and ideal (1) anchors."""
        u = X * self.sigma
        return np.clip((u - self.eta[:, 0]) / (self.eta[:, 5] - self.eta[:, 0]), 0.0, 1.0)

    def from_position(self, P: np.ndarray, round_discrete: bool = True) -> np.ndarray:
        u = self.eta[:, 0] + P * (self.eta[:, 5] - self.eta[:, 0])
        X = u * self.sigma
        if round_discrete:
            for j, st in enumerate(self.step):
                if st:
                    X[..., j] = np.round(X[..., j] / st) * st
        return X

    # ---------------------------------------------------------------- stages
    def normalize(self, X: np.ndarray) -> np.ndarray:
        U = X * self.sigma
        M = np.empty_like(U, dtype=float)
        for j in range(self.d):
            e = self.eta[j]
            m = np.interp(U[:, j], e, self.y)
            for r in range(5):           # exact branch rule of eq. (4)
                sel = (U[:, j] >= e[r]) & (U[:, j] < e[r + 1]) & (e[r] < e[r + 1])
                if sel.any():
                    m[sel] = self.y[r] + (self.y[r + 1] - self.y[r]) * (U[sel, j] - e[r]) / (e[r + 1] - e[r])
            m[U[:, j] < e[0]] = 0.0
            m[U[:, j] >= e[5]] = 1.0
            M[:, j] = m
        return M

    def evaluate(self, X: np.ndarray, mask: np.ndarray | None = None, operator: str | None = None,
                 W: np.ndarray | None = None) -> dict:
        cfg = self.cfg
        op = operator or cfg.operator
        X = np.atleast_2d(np.asarray(X, float))
        n = len(X)
        mask = np.ones_like(X, bool) if mask is None else np.atleast_2d(mask)
        M = self.normalize(np.where(mask, X, 0.0))
        w = self.w if W is None else W
        mus, Ls, Us = [], [], []
        for i, a in enumerate(cfg.actions):
            j = self.action_of == i
            ww = np.broadcast_to(w[..., j] if np.ndim(w) == 2 else w[j], (n, j.sum())) * mask[:, j]
            kappa = ww.sum(1)
            S = (ww * M[:, j]).sum(1) / kappa
            cmask = self.core[j][None, :] & mask[:, j]
            ratio = np.where(cmask, M[:, j] / cfg.theta, np.inf)
            c = ratio.min(1)
            veto = (cmask & (M[:, j] <= 0)).any(1)
            if op == "capped":
                mu, L, U = np.minimum(S, c), np.minimum(kappa * S, c), np.minimum(kappa * S + 1 - kappa, c)
            elif op == "hard":
                g = np.where(veto, 0.0, 1.0)
                mu, L, U = S * g, kappa * S * g, (kappa * S + 1 - kappa) * g
            else:
                mu, L, U = S, kappa * S, kappa * S + 1 - kappa
            mus.append(mu), Ls.append(L), Us.append(U)
        mu, L, U = np.stack(mus, 1), np.stack(Ls, 1), np.stack(Us, 1)
        R = np.zeros(n); RL = np.zeros(n); RU = np.zeros(n)
        goal_mean, goal_min = {}, {}
        for g in cfg.goals:
            idx = [i for i, ga in enumerate(self.goal_of_action) if ga == g]
            goal_mean[g], goal_min[g] = mu[:, idx].mean(1), mu[:, idx].min(1)
            R += cfg.goal_weights[g] * goal_mean[g]
            RL += cfg.goal_weights[g] * L[:, idx].mean(1)
            RU += cfg.goal_weights[g] * U[:, idx].mean(1)
        return {"M": M, "mu": mu, "R": R, "R_min": mu.min(1), "R_L": RL, "R_U": RU,
                "goal_mean": goal_mean, "goal_min": goal_min}
