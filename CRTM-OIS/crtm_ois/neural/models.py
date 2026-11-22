"""Neural solutions around the CRTM-OIS system.

1. NeuralSurrogate      -- (monotone) MLP that learns x -> (R, R_min) from the exact
                           system; used for fast screening and gradient what-if.
2. TelemetryAutoencoder -- data-quality guard: flags implausible measurements
                           (sensor faults) before they reach block B2.
3. ResilienceForecaster -- predicts the integral index h steps ahead from a
                           window of past bus values (early warning).
4. GoalWeightCalibrator -- differentiable, ordinal-logistic calibration of the
                           goal weights omega against expert levels.

The exact system remains the authority: neural outputs are advisory and the
symbolic veto/cap of Stage 4 is never replaced by a learned function.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import levels as lv
from ..fast import BatchEvaluator
from ..model import Configuration
from ..scenarios import e1_values
from .nn import MLP


# ============================================================================ 1
def sample_states(be: BatchEvaluator, n: int, seed: int = 0, p_uniform: float = 0.3,
                  spread: float = 0.35, p_missing: float = 0.04):
    """Random input states around the E1 manifold of rule (12) plus uniform states."""
    rng = np.random.default_rng(seed)
    X0, m0 = be.to_matrix([e1_values()])
    p0 = be.position(np.where(m0, X0, 0.0))[0]
    t = rng.uniform(-1, 1, (n, 1))
    ti = np.clip(t + rng.normal(0, spread, (n, be.d)), -1, 1)
    P = np.where(ti > 0, p0 + ti * (1 - p0), p0 * (1 + ti))
    uni = rng.uniform(size=n) < p_uniform
    P[uni] = rng.uniform(size=(uni.sum(), be.d))
    X = be.from_position(P)
    mask = rng.uniform(size=X.shape) > p_missing
    mask[:, be.core] = True
    mask[:, ~m0[0]] = rng.uniform(size=(n, (~m0[0]).sum())) > 0.5
    # every action keeps at least one observed metric (else E4)
    for i in range(len(be.cfg.actions)):
        j = np.where(be.action_of == i)[0]
        empty = ~mask[:, j].any(1)
        mask[empty, j[0]] = True
    return X, mask, P


class NeuralSurrogate:
    def __init__(self, cfg: Configuration, hidden=(64, 32), monotone: bool = True, seed: int = 0):
        self.cfg = cfg
        self.be = BatchEvaluator(cfg)
        self.monotone = monotone
        self.net = MLP([self.be.d, *hidden, 2], hidden="tanh", out="sigmoid", monotone=monotone, seed=seed)

    def features(self, X, mask):
        P = self.be.position(np.where(mask, X, 0.0))
        return np.where(mask, P, 0.5)

    def fit(self, n: int = 30_000, epochs: int = 150, seed: int = 0, **kw):
        X, mask, _ = sample_states(self.be, n, seed)
        Y = self.be.evaluate(X, mask)
        T = np.stack([Y["R"], Y["R_min"]], 1)
        self.net.fit(self.features(X, mask), T, epochs=epochs, **kw)
        return self

    def predict(self, X, mask=None):
        X = np.atleast_2d(X)
        mask = np.ones_like(X, bool) if mask is None else np.atleast_2d(mask)
        out = self.net.predict(self.features(X, mask))
        return out[:, 0], out[:, 1]

    def predict_sheet(self, sheet: dict) -> dict:
        X, m = self.be.to_matrix([sheet])
        R, Rmin = self.predict(X, m)
        return {"R": float(R[0]), "R_min": float(Rmin[0]), "level": lv.level(float(R[0]))}

    def evaluate(self, n: int = 5000, seed: int = 99) -> dict:
        X, mask, _ = sample_states(self.be, n, seed)
        Y = self.be.evaluate(X, mask)
        R, Rmin = self.predict(X, mask)
        lt, lp = lv.levels(Y["R"]), lv.levels(R)
        conf = np.zeros((5, 5), int)
        for a, b in zip(lt, lp):
            conf[a - 1, b - 1] += 1
        return {"mae_R": float(np.mean(np.abs(R - Y["R"]))),
                "rmse_R": float(np.sqrt(np.mean((R - Y["R"]) ** 2))),
                "mae_Rmin": float(np.mean(np.abs(Rmin - Y["R_min"]))),
                "level_accuracy": float(np.mean(lt == lp)), "confusion": conf,
                "R_true": Y["R"], "R_pred": R, "Rmin_true": Y["R_min"], "Rmin_pred": Rmin,
                "monotone_violations": self.monotonicity_violations(seed=seed)}

    def monotonicity_violations(self, n: int = 2000, seed: int = 7, delta: float = 0.05) -> float:
        rng = np.random.default_rng(seed)
        P = rng.uniform(size=(n, self.be.d))
        j = rng.integers(0, self.be.d, n)
        P2 = P.copy()
        P2[np.arange(n), j] = np.clip(P2[np.arange(n), j] + delta, 0, 1)
        y1, y2 = self.net.predict(P)[:, 0], self.net.predict(P2)[:, 0]
        return float(np.mean(y2 < y1 - 1e-9))

    def sensitivity(self, sheet: dict) -> dict:
        """d R_hat / d position for every metric (neural gradient what-if)."""
        X, m = self.be.to_matrix([sheet])
        F = self.features(X, m)
        net = self.net
        # gradient of first output only
        y, cache, Ws = net.forward(F, keep=True)
        g = np.zeros_like(y); g[:, 0] = 1.0
        from .nn import _act
        for i in range(len(Ws) - 1, -1, -1):
            z, a = cache[i + 1]
            _, df = _act(net.out if i == len(Ws) - 1 else net.hidden)
            g = (g * df(z, a)) @ Ws[i][0].T
        return {k: float(v) for k, v in zip(self.be.keys, g[0])}


# ============================================================================ 2
class TelemetryAutoencoder:
    """Under-complete autoencoder on metric positions; residual z-scores flag faults."""

    def __init__(self, d: int, hidden=(24, 8), seed: int = 0):
        h1, h2 = hidden
        self.net = MLP([d, h1, h2, h1, d], hidden="tanh", out="sigmoid", seed=seed)
        self.thr = None
        self.mean = None

    def fit(self, P: np.ndarray, epochs: int = 300, q: float = 0.995, **kw):
        with np.errstate(all="ignore"):
            self.mean = np.nan_to_num(np.nanmean(P, 0), nan=0.5)
        Pi = np.where(np.isnan(P), self.mean, P)
        self.net.fit(Pi, Pi, epochs=epochs, **kw)
        res = np.abs(self.net.predict(Pi) - Pi)
        self.scale = np.quantile(res, q, axis=0) + 1e-3
        return self

    def score(self, P: np.ndarray) -> np.ndarray:
        P = np.atleast_2d(P)
        miss = np.isnan(P)
        Pi = np.where(miss, self.mean, P)
        z = np.abs(self.net.predict(Pi) - Pi) / self.scale
        z[miss] = 0.0
        return z

    def flag(self, P: np.ndarray, thr: float = 1.5) -> np.ndarray:
        return self.score(P) > thr


# ============================================================================ 3
class ResilienceForecaster:
    """MLP on a sliding window of (R, R_min, goal means) -> R at t + horizon."""

    def __init__(self, window: int = 12, horizon: int = 6, n_feat: int = 6, seed: int = 0):
        self.window, self.horizon, self.n_feat = window, horizon, n_feat
        self.net = MLP([window * n_feat, 48, 16, 1], hidden="tanh", out="sigmoid", seed=seed)

    def windows(self, series: np.ndarray):
        Xs, Ys = [], []
        for t in range(self.window, len(series) - self.horizon + 1):
            Xs.append(series[t - self.window:t].ravel())
            Ys.append(series[t + self.horizon - 1, 0])
        return np.array(Xs), np.array(Ys)

    def fit(self, histories: list[np.ndarray], epochs: int = 300, **kw):
        X, Y = zip(*(self.windows(h) for h in histories))
        self.net.fit(np.vstack(X), np.concatenate(Y), epochs=epochs, **kw)
        return self

    def predict_next(self, recent: np.ndarray) -> float:
        if len(recent) < self.window:
            return float(recent[-1, 0])
        return float(self.net.predict(recent[-self.window:].ravel()[None, :])[0, 0])

    def predict_series(self, series: np.ndarray) -> np.ndarray:
        """Forecast issued at every t (aligned to the target time t + horizon - 1)."""
        out = np.full(len(series), np.nan)
        X, _ = self.windows(np.vstack([series, np.repeat(series[-1:], self.horizon, 0)]))
        pred = self.net.predict(X)[:, 0]
        for i, p in enumerate(pred):
            t = self.window + i + self.horizon - 1
            if t < len(series):
                out[t] = p
        return out


# ============================================================================ 4
@dataclass
class GoalWeightCalibrator:
    """Ordinal-logistic fit of omega (softmax-parameterised) to expert levels.

    P(level >= r | profile) = sigmoid((omega . g - y_{r-1}) / tau), r = 2..5.
    """
    tau: float = 0.04
    lr: float = 0.05
    epochs: int = 3000

    def fit(self, G: np.ndarray, levels: np.ndarray, y=lv.BREAKPOINTS):
        n, k = G.shape
        z = np.zeros(k)
        b = np.asarray(y[1:5])
        Yge = (levels[:, None] >= np.arange(2, 6)[None, :]).astype(float)
        self.loss = []
        for _ in range(self.epochs):
            om = np.exp(z) / np.exp(z).sum()
            R = G @ om
            p = 1 / (1 + np.exp(-(R[:, None] - b[None, :]) / self.tau))
            p = np.clip(p, 1e-6, 1 - 1e-6)
            self.loss.append(float(-np.mean(Yge * np.log(p) + (1 - Yge) * np.log(1 - p))))
            dR = ((p - Yge) / self.tau).sum(1) / n
            g_om = G.T @ dR
            J = np.diag(om) - np.outer(om, om)
            z -= self.lr * 50 * (J @ g_om)
        self.omega = np.exp(z) / np.exp(z).sum()
        return self


def quadratic_kappa(a: np.ndarray, b: np.ndarray, k: int = 5) -> float:
    """Quadratic-weighted Cohen kappa for ordinal levels 1..k."""
    O = np.zeros((k, k))
    for i, j in zip(a, b):
        O[i - 1, j - 1] += 1
    W = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    E = np.outer(O.sum(1), O.sum(0)) / O.sum()
    return float(1 - (W * O).sum() / (W * E).sum()) if (W * E).sum() else 1.0


def synthetic_expert_panel(cfg: Configuration, n: int = 300, true_w=(0.15, 0.40, 0.30, 0.15),
                           noise: float = 0.03, seed: int = 0):
    """SYNTHETIC expert ratings: experts weight goals by `true_w` and add judgment noise.

    Objects are generated with an independent state parameter per goal (rule (12)
    with metric-level jitter), so the goal profiles vary independently over the
    whole scale. Returns goal profiles G (n x 4) and expert levels (1..5). Stands
    in for the expert-comparison study proposed as future work in the manuscript.
    """
    be = BatchEvaluator(cfg)
    rng = np.random.default_rng(seed)
    X0, m0 = be.to_matrix([e1_values()])
    p0 = be.position(np.where(m0, X0, 0.0))[0]
    goal_idx = np.array([cfg.goals.index(cfg.actions[i].goal) for i in be.action_of])
    tg = rng.uniform(-0.9, 0.9, (n, len(cfg.goals)))
    ti = np.clip(tg[:, goal_idx] + rng.normal(0, 0.1, (n, be.d)), -1, 1)
    P = np.where(ti > 0, p0 + ti * (1 - p0), p0 * (1 + ti))
    r = be.evaluate(be.from_position(P), np.repeat(m0, n, 0))
    G = np.column_stack([r["goal_mean"][g] for g in cfg.goals])
    latent = G @ np.asarray(true_w) + rng.normal(0, noise, n)
    return G, lv.levels(np.clip(latent, 0, 1))
