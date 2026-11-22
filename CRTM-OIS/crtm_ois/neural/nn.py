"""Minimal dependency-free neural network library (NumPy) used by the neural agents.

Features: dense layers, tanh/relu/sigmoid/identity activations, Adam, mini-batch
training, early stopping on a validation split, and a *monotone* mode in which
every weight is reparameterised as softplus(v) >= 0. With monotone activations
this makes the network nondecreasing in every input -- the neural counterpart
of adequacy criterion (iii) of the method.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def _act(name):
    if name == "tanh":
        return np.tanh, lambda z, a: 1.0 - a * a
    if name == "relu":
        return (lambda z: np.maximum(z, 0.0)), (lambda z, a: (z > 0).astype(float))
    if name == "sigmoid":
        f = lambda z: 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))
        return f, (lambda z, a: a * (1.0 - a))
    if name == "softplus":
        return (lambda z: np.logaddexp(0.0, z)), (lambda z, a: 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40))))
    if name == "identity":
        return (lambda z: z), (lambda z, a: np.ones_like(z))
    raise ValueError(name)


def _softplus(v):
    return np.logaddexp(0.0, v)


def _sigm(v):
    return 1.0 / (1.0 + np.exp(-np.clip(v, -40, 40)))


@dataclass
class MLP:
    sizes: list
    hidden: str = "tanh"
    out: str = "sigmoid"
    monotone: bool = False
    seed: int = 0
    params: list = field(default_factory=list)
    history: dict = field(default_factory=lambda: {"train": [], "val": []})

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        if not self.params:
            for i, (a, b) in enumerate(zip(self.sizes[:-1], self.sizes[1:])):
                scale = np.sqrt(2.0 / (a + b))
                W = rng.normal(0, scale, (a, b))
                if self.monotone:
                    W = np.log(np.expm1(np.abs(W) + 1e-3))   # inverse softplus
                self.params.append([W, np.zeros(b)])
        self._m = [[np.zeros_like(W), np.zeros_like(b)] for W, b in self.params]
        self._v = [[np.zeros_like(W), np.zeros_like(b)] for W, b in self.params]
        self._t = 0

    # ------------------------------------------------------------------ forward
    def _weights(self):
        return [(_softplus(V) if self.monotone else V, b) for V, b in self.params]

    def forward(self, X, keep=False):
        a = np.asarray(X, float)
        cache = [(None, a)]
        Ws = self._weights()
        for i, (W, b) in enumerate(Ws):
            z = a @ W + b
            f, _ = _act(self.out if i == len(Ws) - 1 else self.hidden)
            a = f(z)
            cache.append((z, a))
        return (a, cache, Ws) if keep else a

    predict = forward

    def input_gradient(self, X):
        """d output / d input (for sensitivity analysis), shape (n, d_in) for 1 output."""
        y, cache, Ws = self.forward(X, keep=True)
        g = np.ones_like(y)
        for i in range(len(Ws) - 1, -1, -1):
            z, a = cache[i + 1]
            _, df = _act(self.out if i == len(Ws) - 1 else self.hidden)
            g = g * df(z, a)
            g = g @ Ws[i][0].T
        return g

    # ------------------------------------------------------------------ training
    def _backward(self, cache, Ws, dY):
        grads = [None] * len(Ws)
        g = dY
        for i in range(len(Ws) - 1, -1, -1):
            z, a = cache[i + 1]
            _, df = _act(self.out if i == len(Ws) - 1 else self.hidden)
            g = g * df(z, a)
            a_prev = cache[i][1]
            gW = a_prev.T @ g
            gb = g.sum(axis=0)
            if self.monotone:
                gW = gW * _sigm(self.params[i][0])
            grads[i] = [gW, gb]
            g = g @ Ws[i][0].T
        return grads

    def fit(self, X, Y, epochs=200, batch=256, lr=3e-3, l2=1e-6, val=0.15, patience=25,
            loss="mse", verbose=False, sample_weight=None):
        X = np.asarray(X, float)
        Y = np.asarray(Y, float).reshape(len(X), -1)
        rng = np.random.default_rng(self.seed + 1)
        idx = rng.permutation(len(X))
        nv = int(len(X) * val)
        vi, ti = idx[:nv], idx[nv:]
        sw = np.ones(len(X)) if sample_weight is None else np.asarray(sample_weight, float)
        best, best_params, wait = np.inf, None, 0
        for ep in range(epochs):
            perm = rng.permutation(ti)
            tot = 0.0
            for s in range(0, len(perm), batch):
                bi = perm[s:s + batch]
                yhat, cache, Ws = self.forward(X[bi], keep=True)
                w = sw[bi][:, None]
                if loss == "bce":
                    p = np.clip(yhat, 1e-7, 1 - 1e-7)
                    dY = w * (p - Y[bi]) / (p * (1 - p)) / len(bi)
                    tot += float(-(w * (Y[bi] * np.log(p) + (1 - Y[bi]) * np.log(1 - p))).sum())
                else:
                    dY = 2 * w * (yhat - Y[bi]) / len(bi)
                    tot += float((w * (yhat - Y[bi]) ** 2).sum())
                grads = self._backward(cache, Ws, dY)
                self._adam(grads, lr, l2)
            tr = tot / max(len(ti), 1)
            vl = float(np.mean((self.forward(X[vi]) - Y[vi]) ** 2)) if nv else tr
            self.history["train"].append(tr)
            self.history["val"].append(vl)
            if verbose and ep % 20 == 0:
                print(f"epoch {ep:4d}  train {tr:.3e}  val {vl:.3e}")
            if vl < best - 1e-9:
                best, wait = vl, 0
                best_params = [[W.copy(), b.copy()] for W, b in self.params]
            else:
                wait += 1
                if wait >= patience:
                    break
        if best_params is not None:
            self.params = best_params
        return self

    def _adam(self, grads, lr, l2, b1=0.9, b2=0.999, eps=1e-8):
        self._t += 1
        for i, (gW, gb) in enumerate(grads):
            for j, g in enumerate((gW + l2 * self.params[i][0], gb)):
                self._m[i][j] = b1 * self._m[i][j] + (1 - b1) * g
                self._v[i][j] = b2 * self._v[i][j] + (1 - b2) * g * g
                mh = self._m[i][j] / (1 - b1 ** self._t)
                vh = self._v[i][j] / (1 - b2 ** self._t)
                self.params[i][j] -= lr * mh / (np.sqrt(vh) + eps)

    # ------------------------------------------------------------------ io
    def n_params(self) -> int:
        return int(sum(W.size + b.size for W, b in self.params))

    def save(self, path):
        arrs = {f"W{i}": W for i, (W, _) in enumerate(self.params)}
        arrs.update({f"b{i}": b for i, (_, b) in enumerate(self.params)})
        np.savez(path, sizes=np.array(self.sizes), hidden=self.hidden, out=self.out,
                 monotone=self.monotone, **arrs)

    @classmethod
    def load(cls, path):
        d = np.load(path, allow_pickle=False)
        n = len(d["sizes"]) - 1
        params = [[d[f"W{i}"], d[f"b{i}"]] for i in range(n)]
        return cls(list(d["sizes"]), str(d["hidden"]), str(d["out"]), bool(d["monotone"]), params=params)
