"""Improvement-advisor agent: exact what-if analysis and a greedy improvement plan.

Candidates act on physical *measurement sources*, so a shared measurement
(AM-DA-1 feeds both Withstand actions) is improved once and moves two metrics
-- the horizontal dependency discussed in Section 4.3 of the manuscript.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .. import levels as lv
from ..fast import BatchEvaluator
from ..model import Configuration


class ImprovementAdvisor:
    def __init__(self, cfg: Configuration, cost: dict | None = None):
        self.cfg = cfg
        self.be = BatchEvaluator(cfg)
        self.cost = cost or {}
        self.sources = defaultdict(list)
        for j, (a, m) in enumerate(self.be.keys):
            src = cfg.action(a).metrics[[x.code for x in cfg.action(a).metrics].index(m)].source
            self.sources[src].append(j)

    def _eval(self, x, mask):
        r = self.be.evaluate(x[None, :], mask[None, :])
        return {k: float(r[k][0]) for k in ("R", "R_min", "R_L", "R_U")}

    def next_boundary(self, j: int, x: float) -> float | None:
        """Physical value at the lower boundary of the next class (None if already high)."""
        u = self.be.sigma[j] * x
        eta = self.be.eta[j]
        for r in range(1, 6):
            if u < eta[r] - 1e-12:
                nxt = eta[r]
                break
        else:
            return None
        xb = self.be.sigma[j] * nxt
        st = self.be.step[j]
        if st:
            xb = np.ceil(xb / st - 1e-9) * st if self.be.sigma[j] > 0 else np.floor(xb / st + 1e-9) * st
        return float(xb)

    def candidates(self, sheet: dict) -> list[dict]:
        X, M = self.be.to_matrix([sheet])
        x, mask = X[0], M[0]
        base = self._eval(x, mask)
        out = []
        for src, js in self.sources.items():
            if not all(mask[j] for j in js):
                continue
            x2 = x.copy()
            ok = False
            for j in js:
                nb = self.next_boundary(j, x[j])
                if nb is not None:
                    x2[j] = nb
                    ok = True
            if not ok:
                continue
            new = self._eval(x2, mask)
            c = float(self.cost.get(src, 1.0))
            out.append({"source": src, "metrics": [self.be.keys[j] for j in js],
                        "from": [float(x[j]) for j in js], "to": [float(x2[j]) for j in js],
                        "dR": new["R"] - base["R"], "dR_L": new["R_L"] - base["R_L"],
                        "dR_min": new["R_min"] - base["R_min"], "cost": c,
                        "gain_per_cost": (new["R"] - base["R"]) / c})
        out.sort(key=lambda d: -d["gain_per_cost"])
        return out

    def missing_value_thresholds(self, sheet: dict, target: float = 0.7) -> list[dict]:
        """For every unreported metric: the value needed to keep R >= target once reported."""
        X, M = self.be.to_matrix([sheet])
        x, mask = X[0], M[0]
        res = []
        for j in np.where(~mask)[0]:
            ps = np.linspace(0, 1, 401)
            Xs = np.repeat(x[None, :], len(ps), 0)
            Xs[:, j] = self.be.from_position(np.tile(ps[:, None], (1, self.be.d)))[:, j]
            Ms = np.repeat(mask[None, :], len(ps), 0)
            Ms[:, j] = True
            R = self.be.evaluate(Xs, Ms)["R"]
            ok = np.where(R >= target)[0]
            res.append({"metric": self.be.keys[j],
                        "R_if_critical": float(R[0]), "R_if_ideal": float(R[-1]),
                        "value_needed": (float(Xs[ok[0], j]) if ok.size else None)})
        return res

    def plan(self, sheet: dict, target_level: int | None = None, max_steps: int = 12,
             require_stable: bool = True) -> dict:
        """Greedy plan: apply the best gain-per-cost step until the target level is reached."""
        X, M = self.be.to_matrix([sheet])
        x, mask = X[0].copy(), M[0]
        cur = self._eval(x, mask)
        target_level = target_level or min(lv.level(cur["R"]) + 1, 5)
        goal = lv.BREAKPOINTS[target_level - 1]
        steps = [{"step": 0, "action": "current state", **cur}]
        sheet_k = dict(sheet)
        for k in range(1, max_steps + 1):
            key = "R_L" if require_stable else "R"
            if cur[key] >= goal:
                break
            cands = self.candidates(sheet_k)
            if not cands:
                break
            cands.sort(key=lambda d: -(d["dR_L"] if require_stable else d["dR"]) / d["cost"])
            best = cands[0]
            for (a, m), v in zip(best["metrics"], best["to"]):
                sheet_k[(a, m)] = v
                x[self.be.keys.index((a, m))] = v
            cur = self._eval(x, mask)
            steps.append({"step": k, "action": best["source"], "metrics": best["metrics"],
                          "from": best["from"], "to": best["to"], **cur})
        return {"target_level": target_level, "target": goal, "steps": steps,
                "reached": cur["R_L" if require_stable else "R"] >= goal, "final_sheet": sheet_k}
