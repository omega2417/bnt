"""
Neural components of the robotic transport complex (pure NumPy, no deep-learning framework).

N1  EnergyEnsemble   deep ensemble (5 MLPs, Gaussian NLL) that predicts the energy of a street
                     segment from telemetry features; its mean and std replace the physics
                     forecast inside the chance constraint of the SFC (strategy "S3N").
N2  PolicyNet        behaviour-cloned supervisory policy (CONTINUE / RETURN / STOP) that runs
                     under a runtime-assurance shield built from the SFC predicates ("NNP").
N3  ContactNet       predicts the probability of mesh contact at a street node from geometry;
                     used for coverage maps, beacon-stop placement and comm-aware routing.
N4  IntentNet        maps a free-text operator request (Ukrainian or English) to a short
                     Meshtastic command; a deterministic validator checks it before sending.

All networks are small multilayer perceptrons trained with Adam on synthetic data.
"""
from __future__ import annotations

import math
import re
import zlib
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import protocol as pr
from .world import RADIO, World, RadioFabric, norm_cdf


# =========================================================================== MLP core
class MLP:
    """Fully connected network: Dense -> act -> ... -> Dense (linear output)."""

    def __init__(self, sizes: Sequence[int], act: str = "relu", seed: int = 0):
        rng = np.random.default_rng(seed)
        self.sizes = list(sizes)
        self.act = act
        self.W, self.b = [], []
        for i, o in zip(sizes[:-1], sizes[1:]):
            scale = math.sqrt(2.0 / i) if act == "relu" else math.sqrt(1.0 / i)
            self.W.append(rng.normal(0, scale, (i, o)))
            self.b.append(np.zeros(o))
        self.mx = self.sx = None
        self.history = []

    # -------------------------------------------------------------- forward / backward
    def _a(self, z):
        return np.maximum(z, 0) if self.act == "relu" else np.tanh(z)

    def _da(self, z, a):
        return (z > 0).astype(float) if self.act == "relu" else 1 - a ** 2

    def forward(self, X):
        cache = [(None, X)]
        h = X
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            z = h @ W + b
            h = z if i == len(self.W) - 1 else self._a(z)
            cache.append((z, h))
        return h, cache

    def backward(self, cache, g):
        gW, gb = [None] * len(self.W), [None] * len(self.W)
        for i in reversed(range(len(self.W))):
            z, a = cache[i + 1]
            if i != len(self.W) - 1:
                g = g * self._da(z, a)
            h_prev = cache[i][1]
            gW[i] = h_prev.T @ g / len(g)
            gb[i] = g.mean(0)
            g = g @ self.W[i].T
        return gW, gb

    def _norm(self, X):
        return (X - self.mx) / self.sx

    # -------------------------------------------------------------- training
    def fit(self, X, Y, loss="mse", epochs=200, batch=256, lr=3e-3, wd=1e-5, val=0.15, seed=0,
            verbose=False, normalize=True):
        X, Y = np.asarray(X, float), np.asarray(Y)
        if normalize:
            self.mx, self.sx = X.mean(0), X.std(0) + 1e-8
        else:
            self.mx, self.sx = np.zeros(X.shape[1]), np.ones(X.shape[1])
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(X))
        nv = int(val * len(X))
        vi, ti = idx[:nv], idx[nv:]
        Xn = self._norm(X)
        params = self.W + self.b
        m = [np.zeros_like(p) for p in params]
        v = [np.zeros_like(p) for p in params]
        step = 0
        b1, b2 = 0.9, 0.999
        for ep in range(epochs):
            rng.shuffle(ti)
            for k in range(0, len(ti), batch):
                bi = ti[k:k + batch]
                out, cache = self.forward(Xn[bi])
                _, g = self._loss(out, Y[bi], loss)
                gW, gb = self.backward(cache, g)
                grads = gW + gb
                step += 1
                for j, (p, gr) in enumerate(zip(params, grads)):
                    if j < len(self.W):
                        gr = gr + wd * p
                    m[j] = b1 * m[j] + (1 - b1) * gr
                    v[j] = b2 * v[j] + (1 - b2) * gr ** 2
                    mh, vh = m[j] / (1 - b1 ** step), v[j] / (1 - b2 ** step)
                    p -= lr * mh / (np.sqrt(vh) + 1e-8)
            if ep % max(1, epochs // 40) == 0 or ep == epochs - 1:
                tr = self._loss(self.forward(Xn[ti[:4000]])[0], Y[ti[:4000]], loss)[0]
                va = self._loss(self.forward(Xn[vi])[0], Y[vi], loss)[0] if nv else np.nan
                self.history.append((ep, tr, va))
                if verbose:
                    print(f"epoch {ep:4d} train {tr:.4f} val {va:.4f}")
        return self

    @staticmethod
    def _loss(out, Y, loss):
        n = len(out)
        if loss == "mse":
            d = out - Y.reshape(out.shape)
            return float((d ** 2).mean()), 2 * d / out.shape[1]
        if loss == "ce":
            z = out - out.max(1, keepdims=True)
            p = np.exp(z)
            p /= p.sum(1, keepdims=True)
            y = Y.astype(int)
            L = -np.log(p[np.arange(n), y] + 1e-12).mean()
            g = p.copy()
            g[np.arange(n), y] -= 1
            return float(L), g
        if loss == "gnll":                     # out = [mean, log variance]
            mu, lv = out[:, 0], np.clip(out[:, 1], -10, 6)
            y = Y.reshape(-1)
            iv = np.exp(-lv)
            L = 0.5 * (lv + (y - mu) ** 2 * iv).mean()
            g = np.zeros_like(out)
            g[:, 0] = -(y - mu) * iv
            g[:, 1] = 0.5 * (1 - (y - mu) ** 2 * iv)
            return float(L), g
        raise ValueError(loss)

    def predict(self, X):
        return self.forward(self._norm(np.asarray(X, float)))[0]

    def n_params(self):
        return int(sum(W.size + b.size for W, b in zip(self.W, self.b)))


def softmax(z):
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(-1, keepdims=True)


# =========================================================================== N1 energy
ENERGY_FEATURES = ["L_250m", "dz_m", "arterial", "local", "unpaved", "snow_fc", "temp_C", "kappa",
                   "payload_kg", "phys_Wh"]


def energy_features(world: World, arcs, kappa, snow_fc, temp, payload):
    arcs = np.asarray(arcs)
    phys = world.arc_energy(arcs, snow_fc, kappa, mass=120 + payload, temp=temp)
    cls = world.arc_cls[arcs]
    n = len(arcs)
    X = np.c_[world.arc_L[arcs] / 250.0, world.arc_dz[arcs], cls == 0, cls == 1, cls == 2,
              np.full(n, snow_fc), np.full(n, temp), np.full(n, kappa), np.full(n, payload), phys]
    return X.astype(float), phys


def make_energy_dataset(world: World, n_scen=160, arcs_per=150, seed=0):
    """Telemetry log: (features, true/physics ratio) from many synthetic shifts."""
    from .sim import Config, Scenario
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    for k in range(n_scen):
        sc = Scenario(world, Config(b=0.0, p_close=0), 10_000 + k)
        arcs = rng.choice(len(world.arc_u), arcs_per, replace=False)
        kap = 1.0 if rng.random() < 0.7 else 0.6
        pay = float(rng.uniform(0, 30))
        X, phys = energy_features(world, arcs, kap, sc.snow_fc, sc.temp, pay)
        true = sc.true_energy(arcs, kap, pay)
        Xs.append(X)
        ys.append(true / phys)
    return np.vstack(Xs), np.concatenate(ys)


class EnergyEnsemble:
    """Deep ensemble of Gaussian MLPs predicting the true/physics energy ratio."""

    def __init__(self, n_members=5, hidden=(32, 32), seed=0):
        self.members = [MLP([len(ENERGY_FEATURES), *hidden, 2], act="tanh", seed=seed + i) for i in range(n_members)]

    def fit(self, X, y, epochs=60, **kw):
        rng = np.random.default_rng(1)
        for i, m in enumerate(self.members):
            bi = rng.integers(0, len(X), len(X))          # bootstrap
            m.fit(X[bi], y[bi], loss="gnll", epochs=epochs, seed=i, **kw)
        return self

    def predict_ratio(self, X):
        outs = np.array([m.predict(X) for m in self.members])     # (M, n, 2)
        mu = outs[..., 0]
        var_a = np.exp(np.clip(outs[..., 1], -10, 6))
        mean = mu.mean(0)
        var = var_a.mean(0) + mu.var(0)                             # aleatoric + epistemic
        return mean, np.sqrt(var), np.sqrt(mu.var(0))

    def __call__(self, world, arcs, kappa, snow_fc, temp, payload):
        """Interface used by the SFC planner: per-arc mean and std of energy (Wh)."""
        X, phys = energy_features(world, arcs, kappa, snow_fc, temp, payload)
        r, sd, _ = self.predict_ratio(X)
        return phys * r, phys * sd


# =========================================================================== N2 policy
POLICY_FEATURES = ["avail/C", "need_D/C", "need_H/C", "need_R/C", "sd_D/C", "z/2.33", "one_way",
                   "r_hat-1", "sigma/30", "contact", "closed", "has_stop", "at_recovery"]
ACTIONS_NN = ["CONTINUE", "RETURN", "STOP"]


def collect_sfc_epochs(world, n=240, seed=0):
    """Run the SFC on random missions and record (features, decision) at each epoch."""
    from .sim import Config, Sim
    rng = np.random.default_rng(seed)
    X, y = [], []
    sites = [f"R{i}" for i in range(1, 9)]
    for k in range(n):
        cfg = Config(H=float(rng.choice([6, 24, 72])), k=int(rng.choice([0, 2, 4, 8])),
                     b=float(rng.choice([0, 0.05, 0.1, 0.2])), soc0=float(rng.uniform(0.2, 0.95)),
                     z=float(rng.choice([0.67, 1.28, 1.645, 2.33])), oneway=bool(rng.random() < 0.2),
                     tasks=[dict(site=str(rng.choice(sites)), alt="R5")], strategy="S3")
        sim = Sim(world, cfg, seed=20_000 + k, log_epochs=True)
        sim.run()
        for f, lab in sim.epoch_log:
            if f[11] < 0.5:            # only epochs with an open delivery (the real decision)
                continue
            X.append(f)
            y.append(ACTIONS_NN.index(lab))
    return np.array(X), np.array(y)


class PolicyNet:
    def __init__(self, hidden=(64, 32), seed=0):
        self.net = MLP([len(POLICY_FEATURES), *hidden, len(ACTIONS_NN)], act="relu", seed=seed)

    def fit(self, X, y, epochs=150, **kw):
        # class re-weighting by oversampling rare decisions
        counts = np.bincount(y, minlength=len(ACTIONS_NN))
        rng = np.random.default_rng(0)
        idx = np.concatenate([rng.choice(np.where(y == c)[0], max(counts.max() // 3, counts[c]), replace=True)
                              if counts[c] else np.array([], int) for c in range(len(ACTIONS_NN))])
        self.net.fit(X[idx], y[idx], loss="ce", epochs=epochs, **kw)
        return self

    def proba(self, X):
        return softmax(self.net.predict(np.atleast_2d(X)))

    def act(self, f):
        return ACTIONS_NN[int(np.argmax(self.proba(f)[0]))]


# =========================================================================== N3 contact
CONTACT_FEATURES = ["d_gw_km", "d_inf_km", "h_inf/25", "n_inf_1km", "z/50", "dshore_km", "k/8", "H/72"]


def contact_features(world: World, fab: RadioFabric, alive, H):
    xy = world.xy
    inf_xy = np.array([world.xy[n] for (_, n, _) in fab.infra])
    hs = np.array([h for (_, _, h) in fab.infra])
    D = np.linalg.norm(xy[:, None, :] - inf_xy[None], axis=2) / 1000.0
    D = np.where(alive[None, :], D, 99.0)
    j = D.argmin(1)
    return np.c_[D[:, 0], D.min(1), hs[j] / 25.0, (D < 1.0).sum(1), world.z / 50.0,
                 world.dshore / 1000.0, np.full(world.n, fab.k / 8.0), np.full(world.n, H / 72.0)]


def make_contact_dataset(world, n_scen=60, checks=3, seed=0):
    from .sim import Config, Scenario
    rng = np.random.default_rng(seed)
    X, y = [], []
    for s in range(n_scen):
        cfg = Config(H=float(rng.choice([6, 24, 48, 72])), k=int(rng.choice([0, 2, 4, 8])), b=0)
        sc = Scenario(world, cfg, 30_000 + s)
        F = contact_features(world, sc.fab, sc.alive, cfg.H)
        for _ in range(checks):
            ok = sc.best_margin + rng.normal(0, RADIO["fading"], world.n) > 0
            X.append(F)
            y.append(ok.astype(int))
    return np.vstack(X), np.concatenate(y)


class ContactNet:
    def __init__(self, hidden=(32, 16), seed=0):
        self.net = MLP([len(CONTACT_FEATURES), *hidden, 2], act="relu", seed=seed)

    def fit(self, X, y, epochs=40, **kw):
        self.net.fit(X, y, loss="ce", epochs=epochs, **kw)
        return self

    def proba(self, X):
        return softmax(self.net.predict(X))[:, 1]


# =========================================================================== N4 intents
INTENTS = ["TASK", "CLOSE", "RECALL", "HOLD", "RISK", "RELAY", "REPORT"]

_TEMPLATES = {
    "TASK": [
        "терміново доставити {cargo} до {R}, резерв {R2}, до {hh}:{mm}",
        "відвезіть {cargo} у пункт {R} до {hh}:{mm}, якщо закрито то {R2}",
        "потрібна доставка {cargo} {R} запасний {R2}",
        "доставка {cargo}: {R}, альтернатива {R2}, дедлайн {hh}{mm}",
        "deliver {cargo_en} to {R} by {hh}:{mm}, fallback {R2}",
        "urgent {cargo_en} for site {R}, alternate {R2}",
        "send a robot with {cargo_en} to {R} before {hh}:{mm}",
        "{R} просить {cargo}, якнайшвидше, резервний пункт {R2}",
        "завдання: {cargo} -> {R} (альт. {R2}) до {hh}:{mm}",
        "dispatch {cargo_en} to {R}, if closed go to {R2}",
    ],
    "CLOSE": [
        "пункт {R} закрито, перенаправляйте на {R2}",
        "{R} більше не працює, альтернатива {R2}",
        "закриття {R}, нова адреса видачі {R2}",
        "site {R} is closed, use {R2}",
        "{R} shut down, redirect deliveries to {R2}",
        "у {R} немає персоналу, везіть у {R2}",
        "close {R}; alternative {R2}",
    ],
    "RECALL": [
        "робот {U} негайно повернутись до {P}",
        "відкликати {U} на {P}",
        "{U} назад на базу {P}",
        "recall {U} to {P}",
        "{U} return to {P} immediately",
        "повернути {U} у пункт повернення {P}",
        "abort mission of {U}, go to {P}",
    ],
    "HOLD": [
        "{U} зачекати {n} хвилин",
        "утримувати {U} на місці {n} хв",
        "{U} стоп на {n} хвилин, пропускаємо колону",
        "hold {U} for {n} minutes",
        "{U} wait {n} min",
        "pause {U} {n} minutes",
    ],
    "RISK": [
        "встановити рівень ризику {zf}",
        "обережніше, z = {zf}",
        "ризик {zf} для всіх роботів",
        "set risk level to {zf}",
        "risk dial {zf}",
        "z {zf} for all units",
    ],
    "RELAY": [
        "ретранслятор {U} розгорнути у вузлі {N}",
        "підняти щоглу {U} на вузлі {N}",
        "відправити ретранслятор {U} до точки {N}",
        "deploy relay {U} at node {N}",
        "move relay robot {U} to {N} and raise mast",
    ],
    "REPORT": [
        "звіти тільки за подіями",
        "перейти на звіти за подіями, економимо ефір",
        "статус кожні {n} хвилин",
        "event-driven reporting only",
        "report every {n} minutes",
        "зменшити трафік, тільки події",
    ],
}
_CARGO_UA = ["інсулін", "ліки", "воду", "питну воду", "дитяче харчування", "антибіотики", "продукти"]
_CARGO_EN = ["insulin", "medicine", "water", "drinking water", "infant formula", "antibiotics", "food"]
_CARGO_CODE = {"інсулін": 1, "ліки": 1, "антибіотики": 1, "воду": 2, "питну": 2, "дитяче": 4,
               "продукти": 3, "insulin": 1, "medicine": 1, "antibiotics": 1, "water": 2, "infant": 4, "food": 3}


def _fill(tpl, rng):
    r1, r2 = rng.choice(8, 2, replace=False) + 1
    return tpl.format(cargo=rng.choice(_CARGO_UA), cargo_en=rng.choice(_CARGO_EN), R=f"R{r1}", R2=f"R{r2}",
                      hh=f"{rng.integers(8, 20):02d}", mm=f"{rng.choice([0, 10, 15, 20, 30, 40, 45, 50]):02d}",
                      U=f"U{rng.integers(1, 9)}", P=str(rng.choice(["P1", "P2", "P3", "H0"])),
                      n=int(rng.choice([5, 10, 15, 20, 30])), zf=str(rng.choice(["0.67", "1.28", "1.64", "2.33"])),
                      N=int(rng.integers(0, 480)))


def _typo(s, rng, p=0.04):
    out = []
    for ch in s:
        r = rng.random()
        if r < p / 2:
            continue
        out.append(ch)
        if r > 1 - p / 2:
            out.append(ch)
    return "".join(out)


def make_intent_dataset(n_per=220, seed=0, test_frac=0.2):
    """Synthetic operator requests (UA + EN, 50 % with typos), random train/test split."""
    rng = np.random.default_rng(seed)
    data = []
    for it, tpls in _TEMPLATES.items():
        for tpl in tpls:
            for _ in range(n_per // len(tpls) + 4):
                s = _fill(tpl, rng)
                data.append((_typo(s, rng) if rng.random() < 0.5 else s, INTENTS.index(it)))
    idx = rng.permutation(len(data))
    nt = int(test_frac * len(data))
    return [data[i] for i in idx[nt:]], [data[i] for i in idx[:nt]]


# phrasings never seen in training: used to show confidence gating
UNSEEN = [
    "R3 out of service, everything goes to R5 now",
    "U2 come back to P1, battery is low",
    "R4 потребує антибіотики до 16:00, запасний R6",
    "щогла U9 на вузол 210",
    "ризик знизити до 0.67",
    "U5 почекай 20 хв",
    "пункт R8 зачинився, видача в R2",
    "звітуйте раз на 15 хвилин",
]


def text_features(texts, dim=1024):
    """Hashed character 2-4-grams + word unigrams (language independent)."""
    X = np.zeros((len(texts), dim))
    for i, s in enumerate(texts):
        s = " " + re.sub(r"[RPUNrpun]\d+", " # ", s.lower()) + " "
        s = re.sub(r"\d", "0", s)
        words = re.findall(r"\w+", s)
        grams = [s[j:j + n] for n in (3, 4) for j in range(len(s) - n + 1)]
        grams += ["w:" + wd for wd in words] + ["s:" + wd[:4] for wd in words if len(wd) > 3]
        for g in grams:
            X[i, zlib.crc32(g.encode()) % dim] += 1.0
        X[i] /= max(1.0, np.linalg.norm(X[i]))
    return X


class IntentNet:
    def __init__(self, dim=1024, hidden=(64,), seed=0):
        self.dim = dim
        self.net = MLP([dim, *hidden, len(INTENTS)], act="relu", seed=seed)

    def fit(self, data, epochs=40, **kw):
        X = text_features([s for s, _ in data], self.dim)
        y = np.array([c for _, c in data])
        self.net.fit(X, y, loss="ce", epochs=epochs, normalize=False, **kw)
        return self

    def proba(self, texts):
        return softmax(self.net.predict(text_features(texts, self.dim)))

    def classify(self, text):
        p = self.proba([text])[0]
        return INTENTS[int(p.argmax())], float(p.max())

    # ------------------------------------------------------------------ slots -> command
    @staticmethod
    def slots(text):
        t = text.upper()
        R = [int(x) for x in re.findall(r"\bR(\d)\b", t)]
        U = [int(x) for x in re.findall(r"\bU(\d+)\b", t)]
        P = re.findall(r"\b(P\d|H0)\b", t)
        N = [int(x) for x in re.findall(r"\bN(?:ODE)?\s*(\d+)\b", t)] or \
            [int(x) for x in re.findall(r"(?:ВУЗ\w*|ТОЧК\w*|NODE)\s+(\d+)", t)]
        tm = re.search(r"\b(\d{1,2})[:.]?(\d{2})\b", t)
        mins = re.search(r"(\d+)\s*(?:ХВ|MIN)", t)
        z = re.search(r"(\d\.\d+)", t)
        cargo = 1
        for k, v in _CARGO_CODE.items():
            if k.upper() in t:
                cargo = v
                break
        return dict(R=R, U=U, P=P, N=N, time=(int(tm.group(1)) * 60 + int(tm.group(2))) if tm else None,
                    minutes=int(mins.group(1)) if mins else None, z=float(z.group(1)) if z else None,
                    cargo=cargo, urgent=any(w in t for w in ("ТЕРМІН", "URGENT", "НЕГАЙНО", "ЯКНАЙШВИДШЕ")))

    def to_command(self, text, task_id=100, now_min=8 * 60):
        """Free text -> (intent, confidence, Command or None, validation errors)."""
        intent, conf = self.classify(text)
        s = self.slots(text)
        cmd = None
        try:
            if intent == "TASK":
                site = s["R"][0]
                alt = s["R"][1] if len(s["R"]) > 1 else (site % 8) + 1
                dl = s["time"] if s["time"] is not None else now_min + 120
                cmd = pr.TSK(task_id, site, alt, dl, z=1.64 if s["urgent"] else 1.28)
            elif intent == "CLOSE":
                cmd = pr.CLS(s["R"][0], s["R"][1])
            elif intent == "RECALL":
                cmd = pr.RTB(s["U"][0], pr.POINT_CODES.get(s["P"][0] if s["P"] else "H0", 0))
            elif intent == "HOLD":
                cmd = pr.HLD(s["U"][0], s["minutes"] or 10)
            elif intent == "RISK":
                cmd = pr.ZSET(s["z"] if s["z"] is not None else 1.28)
            elif intent == "RELAY":
                cmd = pr.RLY(s["U"][0], s["N"][0] if s["N"] else 0)
            elif intent == "REPORT":
                cmd = pr.RPT(0 if s["minutes"] is None else s["minutes"])
        except (IndexError, KeyError):
            return intent, conf, None, ["missing slot"]
        errs = pr.validate(cmd) if cmd is not None else ["no command"]
        if conf < 0.6:
            errs = errs + ["low confidence: ask operator to confirm"]
        return intent, conf, cmd, errs
