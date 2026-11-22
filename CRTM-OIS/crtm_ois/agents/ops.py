"""Operational agents around the block team and the multi-agent orchestrator.

Topology (topics in brackets):

  TelemetryAgent --[telemetry]--> SurrogateAgent --[nowcast]
                               \-> DataQualityAgent --(CU.start)--> [sheet] B0 ... B8 --[report]
  [report] --> WatchdogAgent --[alert]
  [report] --> ForecastAgent --[forecast] --> WatchdogAgent
  [alert]  --> AdvisorAgent  --[advice]
"""
from __future__ import annotations

import numpy as np

from .. import levels as lv
from ..fast import BatchEvaluator
from ..model import Configuration
from ..neural.models import (NeuralSurrogate, ResilienceForecaster, TelemetryAutoencoder)
from .advisor import ImprovementAdvisor
from .blocks import build_block_team
from .bus import Agent, Message, MessageBus
from .twin import DigitalTwin


class TelemetryAgent(Agent):
    name = "TEL"
    role = "Telemetry / digital twin interface"

    def __init__(self, bus, twin: DigitalTwin):
        super().__init__(bus)
        self.twin = twin

    def tick(self) -> dict:
        obs = self.twin.step()
        self.bus.tick = obs["t"]
        self.send("telemetry", obs)
        return obs


class DataQualityAgent(Agent):
    """Neural guard: autoencoder flags faulty readings before block B0.

    Non-core flagged readings are withheld (reported as missing -> enclosure);
    a flagged core reading is replaced by the last validated value and marked,
    because a missing core metric would stop the chain with E3.
    """
    name = "DQ"
    role = "Data-quality guard (autoencoder)"

    def __init__(self, bus, cu, be: BatchEvaluator, ae: TelemetryAutoencoder | None, thr: float = 1.5,
                 jump: float = 0.45, persist: int = 3):
        super().__init__(bus)
        self.cu, self.be, self.ae, self.thr = cu, be, ae, thr
        self.jump, self.persist = jump, persist
        self.last_good = {}
        self._jumped = {}
        self.flags = []
        self.on("telemetry", self._on)

    def _on(self, msg: Message):
        sheet = dict(msg.payload["sheet"])
        X, M = self.be.to_matrix([sheet])
        P = np.where(M, self.be.position(np.where(M, X, 0.0)), np.nan)
        flagged = np.zeros(self.be.d, bool) if self.ae is None else self.ae.flag(P, self.thr)[0]
        # symbolic rule for core metrics: a jump larger than `jump` (in position units) is held
        # until it persists for `persist` ticks -- a real outage persists, a glitch does not
        for j in np.where(self.be.core)[0]:
            k = self.be.keys[j]
            if sheet[k] is None or k not in self.last_good:
                continue
            p_old = self.be.position(np.array([[self.last_good[kk] if kk in self.last_good else 0.0
                                                for kk in self.be.keys]]))[0, j]
            if abs(P[0, j] - p_old) > self.jump:
                self._jumped[k] = self._jumped.get(k, 0) + 1
                flagged[j] = self._jumped[k] < self.persist
            else:
                self._jumped[k] = 0
        held, withheld = [], []
        for j, k in enumerate(self.be.keys):
            if flagged[j] and sheet[k] is not None:
                if self.be.core[j] and k in self.last_good:
                    sheet[k] = self.last_good[k]
                    held.append(k)
                elif not self.be.core[j]:
                    sheet[k] = None
                    withheld.append(k)
            elif sheet[k] is not None:
                self.last_good[k] = sheet[k]
        self.flags.append(flagged)
        if held or withheld:
            self.send("dq", {"held": held, "withheld": withheld})
        self.cu.start(sheet)


class SurrogateAgent(Agent):
    name = "NN"
    role = "Neural nowcast (monotone surrogate)"

    def __init__(self, bus, surrogate: NeuralSurrogate):
        super().__init__(bus)
        self.s = surrogate
        self.on("telemetry", lambda m: self.send("nowcast", self.s.predict_sheet(m.payload["sheet"])))


class ForecastAgent(Agent):
    name = "FC"
    role = "Neural forecaster (early warning)"

    def __init__(self, bus, fc: ResilienceForecaster | None):
        super().__init__(bus)
        self.fc = fc
        self.hist = []
        self.on("report", self._on)

    def _on(self, msg):
        r = msg.payload
        self.hist.append([r["R"], r["R_min"], *r["goals"]])
        if self.fc is not None:
            pred = self.fc.predict_next(np.array(self.hist))
            self.send("forecast", {"R_hat": pred, "horizon": self.fc.horizon, "level_hat": lv.level(pred)})


class WatchdogAgent(Agent):
    """Rule-based monitor of the verdict with hysteresis and per-kind cooldown.

    A level change is confirmed only after it persists for `persist` ticks, so a
    verdict that sits on a boundary (as E1 does) does not produce an alert storm.
    """
    name = "WD"
    role = "Resilience watchdog"

    def __init__(self, bus, share_thr: float = 0.8, persist: int = 3, cooldown: int = 15):
        super().__init__(bus)
        self.share_thr, self.persist, self.cooldown = share_thr, persist, cooldown
        self.confirmed = None
        self.candidate, self.count = None, 0
        self.prev = None
        self.alerts = []
        self._last = {}
        self.on("report", self._on_report)
        self.on("forecast", self._on_fc)

    def _alert(self, kind, text, severity, **kw):
        t = self.bus.tick
        if kind in self._last and t - self._last[kind] < self.cooldown:
            return
        self._last[kind] = t
        a = {"tick": t, "kind": kind, "text": text, "severity": severity, **kw}
        self.alerts.append(a)
        self.send("alert", a)

    def _on_report(self, msg):
        r = msg.payload
        lev = r["level"]
        if self.confirmed is None:
            self.confirmed = lev
        elif lev != self.confirmed:
            self.count = self.count + 1 if lev == self.candidate else 1
            self.candidate = lev
            if self.count >= self.persist:
                d = "drop" if lev < self.confirmed else "rise"
                self._last.pop(f"level_{d}", None)
                self._alert(f"level_{d}", f"level {lv.code(self.confirmed)} -> {r['level_code']}",
                            "serious" if d == "drop" else "info")
                self.confirmed, self.count = lev, 0
        else:
            self.count = 0
        newly = set(r["vetoed"]) - set(self.prev["vetoed"] if self.prev else [])
        for v in sorted(newly):
            self._last.pop("veto", None)
            self._alert("veto", f"core capability lost in {v}", "critical", action=v)
        if not r["stable_missing"]:
            self._alert("unstable", "missing-data enclosure crosses a level boundary", "warning")
        P = r.get("P") or {}
        if "shares" in P and max(P["shares"].values()) < self.share_thr:
            self._alert("weights", f"verdict sensitive to weights (top share {max(P['shares'].values()):.0%})",
                        "warning")
        self.prev = r

    def _on_fc(self, msg):
        f = msg.payload
        if self.confirmed is not None and f["level_hat"] < self.confirmed:
            self._alert("forecast_drop", f"forecast R={f['R_hat']:.3f} in {f['horizon']} ticks "
                        f"(level {lv.code(f['level_hat'])})", "warning")


class AdvisorAgent(Agent):
    name = "ADV"
    role = "Improvement advisor"

    def __init__(self, bus, cfg, telemetry_ref):
        super().__init__(bus)
        self.adv = ImprovementAdvisor(cfg)
        self.ref = telemetry_ref
        self.advice = []
        self.on("alert", self._on)

    def _on(self, msg):
        if msg.payload["severity"] not in ("serious", "critical"):
            return
        sheet = self.ref.last_sheet
        if sheet is None:
            return
        cands = self.adv.candidates(sheet)[:3]
        a = {"tick": self.bus.tick, "trigger": msg.payload["kind"],
             "top": [(c["source"], round(c["dR"], 4)) for c in cands]}
        self.advice.append(a)
        self.send("advice", a)


class _SheetRef:
    def __init__(self, bus):
        self.last_sheet = None
        bus.subscribe("sheet", lambda m: setattr(self, "last_sheet", m.payload))


class ResilienceOperationsCenter:
    """Multi-agent system: block team B0-B8 + CU plus operational and neural agents."""

    def __init__(self, cfg: Configuration, seed: int = 0, mc_samples: int = 5000,
                 surrogate: NeuralSurrogate | None = None, ae: TelemetryAutoencoder | None = None,
                 forecaster: ResilienceForecaster | None = None, twin: DigitalTwin | None = None):
        self.cfg = cfg
        self.bus = MessageBus()
        self.ref, self.cu, self.blocks = build_block_team(self.bus, cfg, mc_samples)
        self.be = BatchEvaluator(cfg)
        self.twin = twin or DigitalTwin(cfg, seed=seed)
        self.tel = TelemetryAgent(self.bus, self.twin)
        self.dq = DataQualityAgent(self.bus, self.cu, self.be, ae)
        self.nn = SurrogateAgent(self.bus, surrogate) if surrogate else None
        self.fc = ForecastAgent(self.bus, forecaster)
        self.wd = WatchdogAgent(self.bus)
        self.sheet_ref = _SheetRef(self.bus)
        self.adv = AdvisorAgent(self.bus, cfg, self.sheet_ref)
        self.reports, self.nowcasts, self.forecasts, self.obs = [], [], [], []
        self.bus.subscribe("report", lambda m: self.reports.append(m.payload))
        self.bus.subscribe("nowcast", lambda m: self.nowcasts.append(m.payload))
        self.bus.subscribe("forecast", lambda m: self.forecasts.append(m.payload))

    @property
    def agents(self) -> list:
        ag = [self.tel, self.dq] + ([self.nn] if self.nn else []) + [self.cu, *self.blocks, self.fc, self.wd, self.adv]
        return ag

    def run(self, ticks: int) -> dict:
        for _ in range(ticks):
            self.obs.append(self.tel.tick())
        return self.history()

    def history(self) -> dict:
        reps = self.reports
        h = {k: np.array([r[k] for r in reps]) for k in ("R", "R_min", "R_L", "R_U", "level")}
        h["t"] = np.array([r["tick"] for r in reps])
        h["goals"] = np.array([r["goals"] for r in reps])
        h["vetoed"] = [r["vetoed"] for r in reps]
        h["share_top"] = np.array([max(r["P"]["shares"].values()) if "shares" in r["P"] else np.nan for r in reps])
        h["nowcast"] = np.array([n["R"] for n in self.nowcasts]) if self.nowcasts else None
        h["forecast"] = np.array([f["R_hat"] for f in self.forecasts]) if self.forecasts else None
        h["alerts"] = self.wd.alerts
        h["advice"] = self.adv.advice
        h["faults"] = np.array([o["fault"] for o in self.obs])
        h["flags"] = np.array(self.dq.flags)
        h["events"] = [(e.name, e.start, e.end) for e in self.twin.events]
        return h


# ---------------------------------------------------------------- training helpers
def exact_history(cfg: Configuration, seed: int, ticks: int, clean: bool = True) -> np.ndarray:
    """Exact (R, R_min, goal means) series of a twin run, for forecaster training."""
    twin = DigitalTwin(cfg, seed=seed)
    if clean:
        twin.p_spike = twin.p_stuck_start = twin.p_missing = 0.0
    be = twin.be
    rng = np.random.default_rng(seed + 100)
    for ev in twin.events:                         # randomise event timing between episodes
        shift = int(rng.integers(-30, 30))
        ev.start, ev.end = max(ev.start + shift, 5), ev.end + shift
    obs = twin.run(ticks)
    X, M = be.to_matrix([o["sheet"] for o in obs])
    r = be.evaluate(X, M)
    return np.column_stack([r["R"], r["R_min"], *[r["goal_mean"][g] for g in cfg.goals]])


def train_neural_agents(cfg: Configuration, seed: int = 0, n_surrogate: int = 30_000,
                        ticks: int = 220, episodes: int = 12, verbose: bool = False):
    sur = NeuralSurrogate(cfg, monotone=True, seed=seed).fit(n=n_surrogate, epochs=150, seed=seed)
    twin = DigitalTwin(cfg, seed=seed + 1000)
    twin.p_spike = twin.p_stuck_start = 0.0
    obs = twin.run(400)
    X, M = twin.be.to_matrix([o["sheet"] for o in obs])
    P = np.where(M, twin.be.position(np.where(M, X, 0.0)), np.nan)
    P[:, twin.never] = np.nan
    ae = TelemetryAutoencoder(twin.be.d, seed=seed).fit(P, epochs=300)
    hist = [exact_history(cfg, seed + 2000 + k, ticks) for k in range(episodes)]
    fc = ResilienceForecaster(seed=seed).fit(hist, epochs=300)
    return sur, ae, fc
