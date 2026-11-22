"""LLM-agent interface: the system as a set of tools for an analyst agent.

* `ResilienceToolbox` -- pure-Python tools with JSON schemas (assess, explain,
  what-if, recommend, trace, robustness). Usable by any agent framework.
* `ClaudeAnalyst`    -- an analyst agent on the Claude API (Anthropic SDK tool
  runner). It needs the `anthropic` package and credentials; every number it
  reports comes from the tools, i.e. from the exact system.
* `OfflineAnalyst`   -- a deterministic analyst that calls the same tools and
  writes a structured report without any network access (used in tests and in
  the demo notebook).
"""
from __future__ import annotations

import json
from typing import Any

from .. import levels as lv
from ..model import GOAL_NAMES, Configuration
from ..scenarios import five_states
from ..system import AssessmentError, assess
from .advisor import ImprovementAdvisor

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are a cyber-resilience analyst for critical infrastructure.
You work with CRTM-OIS, a deterministic system that computes the integral cyber
resilience index R of an object from metric measurements (seven stages,
non-compensatory aggregation, five levels C/BA/A/AA/H).
Rules:
- Every number you state must come from a tool result; never estimate scores yourself.
- Always report R together with its level, the weakest-link index R_min, the
  missing-data enclosure [R_L, R_U] and the weight-robustness shares.
- If the enclosure crosses a level boundary or the top level share is below 80%,
  say that the verdict is not stable and explain why.
- Distinguish verification of the implementation from validity on real objects:
  the scenario data are illustrative, not field data.
Answer in the language of the user's question."""


def _r(x, n=4):
    return None if x is None else round(float(x), n)


class ResilienceToolbox:
    """State-holding tool set around one configuration and one current input sheet."""

    def __init__(self, cfg: Configuration, sheet: dict | None = None, mc_samples: int = 20_000):
        self.cfg = cfg
        self.states = five_states(cfg)
        self.sheet = dict(sheet or self.states["E1"])
        self.mc = mc_samples
        self.adv = ImprovementAdvisor(cfg)
        self.calls: list[dict] = []

    # ---------------------------------------------------------------- helpers
    def _key(self, action: str, metric: str):
        k = (action, metric)
        if k not in self.sheet:
            raise KeyError(f"unknown metric {action}.{metric}")
        return k

    def _log(self, name, args, out):
        self.calls.append({"tool": name, "args": args, "result": out})
        return out

    # ---------------------------------------------------------------- tools
    def load_state(self, state: str) -> dict:
        """Load one of the input states E1..E5 of the adequacy experiment."""
        if state not in self.states:
            return self._log("load_state", {"state": state}, {"error": f"unknown state {state}"})
        self.sheet = dict(self.states[state])
        return self._log("load_state", {"state": state}, {"loaded": state, "n_metrics": len(self.sheet)})

    def assess_current(self) -> dict:
        """Run the seven stages on the current sheet and return the structured verdict."""
        try:
            r = assess(self.cfg, self.sheet, n=self.mc)
        except AssessmentError as e:
            return self._log("assess_current", {}, {"failure_code": e.code, "detail": e.detail})
        P = r.P
        out = {"R": _r(r.R["R"]), "level": r.R["level_code"], "level_name": r.R["level_name"],
               "R_min": _r(r.R["R_min"]), "level_min": lv.code(r.R["level_min"]),
               "enclosure": [_r(r.R["R_L"]), _r(r.R["R_U"])],
               "stable_wrt_missing_data": r.R["stable_missing"],
               "weakest_goal": GOAL_NAMES[r.R["weakest_goal"]], "weakest_action": r.R["weakest_action"],
               "vetoed_actions": r.R["vetoed"], "capped_actions": r.R["capped"],
               "incomplete_actions": r.R["incomplete"],
               "goals_mean": {GOAL_NAMES[g]: _r(r.G[g]["mean"]) for g in r.G},
               "goals_min": {GOAL_NAMES[g]: _r(r.G[g]["min"]) for g in r.G},
               "actions": {c: {"mu": _r(a["mu"]), "level": lv.code(a["level"]), "kappa": _r(a["kappa"], 3)}
                           for c, a in r.A.items()},
               "robustness": {"mean": _r(P["mean"]), "sd": _r(P["sd"]),
                              "q05_q95": [_r(P["q05"]), _r(P["q95"])],
                              "level_shares": {k: _r(v, 4) for k, v in P["shares"].items() if v > 0},
                              "rho": P["rho"], "samples": P["n"]},
               "config_version": self.cfg.version}
        return self._log("assess_current", {}, out)

    def explain_action(self, action: str) -> dict:
        """Bus-level explanation of one basic action: values, class tables, scores, cap."""
        r = assess(self.cfg, self.sheet, robust=False)
        a = self.cfg.action(action)
        rows = []
        for m in a.metrics:
            k = (a.code, m.code)
            s = r.norm["M"][k]
            rows.append({"metric": m.code, "name": m.name, "unit": m.unit, "x": self.sheet[k],
                         "class_table": list(m.xi), "core": m.core, "weight": _r(m.weight),
                         "m": _r(s), "level": None if s is None else lv.code(lv.level(s))})
        rec = r.A[action]
        out = {"action": action, "name": a.name, "goal": GOAL_NAMES[a.goal], "metrics": rows,
               "S": _r(rec["S"]), "cap": None if rec["c"] == float("inf") else _r(rec["c"]),
               "mu": _r(rec["mu"]), "level": lv.code(rec["level"]), "enclosure": [_r(rec["L"]), _r(rec["U"])],
               "veto": rec["veto"], "cap_active": rec["cap_active"], "kappa": _r(rec["kappa"], 3)}
        return self._log("explain_action", {"action": action}, out)

    def what_if(self, action: str, metric: str, value: float | None) -> dict:
        """Change one measurement (None = not reported) and compare the verdict before/after."""
        k = self._key(action, metric)
        before = assess(self.cfg, self.sheet, robust=False).R
        trial = dict(self.sheet)
        src = self.cfg.action(action).metrics[[m.code for m in self.cfg.action(action).metrics].index(metric)].source
        for (a2, m2) in trial:                       # shared measurement moves together
            mm = self.cfg.action(a2).metrics[[m.code for m in self.cfg.action(a2).metrics].index(m2)]
            if mm.source == src:
                trial[(a2, m2)] = value
        try:
            after = assess(self.cfg, trial, robust=False).R
        except AssessmentError as e:
            return self._log("what_if", {"action": action, "metric": metric, "value": value},
                             {"failure_code": e.code, "detail": e.detail})
        out = {"changed": f"{action}.{metric}", "from": self.sheet[k], "to": value,
               "shared_with": [f"{a}.{m}" for (a, m) in trial if trial[(a, m)] != self.sheet[(a, m)] and (a, m) != k],
               "R": [_r(before["R"]), _r(after["R"])],
               "level": [before["level_code"], after["level_code"]],
               "R_min": [_r(before["R_min"]), _r(after["R_min"])],
               "enclosure_after": [_r(after["R_L"]), _r(after["R_U"])],
               "vetoed_after": after["vetoed"]}
        return self._log("what_if", {"action": action, "metric": metric, "value": value}, out)

    def recommend(self, target_level: str | None = None) -> dict:
        """Greedy improvement plan to reach a target level with a stable verdict."""
        tl = None if target_level is None else lv.LEVEL_CODES.index(target_level) + 1
        p = self.adv.plan(self.sheet, tl)
        miss = self.adv.missing_value_thresholds(self.sheet, lv.BREAKPOINTS[p["target_level"] - 1])
        out = {"target_level": lv.code(p["target_level"]), "reached": p["reached"],
               "steps": [{"step": s["step"], "measurement": s["action"],
                          "to": s.get("to"), "R": _r(s["R"]), "R_L": _r(s["R_L"]), "R_min": _r(s["R_min"])}
                         for s in p["steps"]],
               "top_single_steps": [{"measurement": c["source"], "from": c["from"], "to": c["to"],
                                     "dR": _r(c["dR"]), "dR_L": _r(c["dR_L"])}
                                    for c in self.adv.candidates(self.sheet)[:5]],
               "missing_values": [{"metric": ".".join(m["metric"]), "value_needed": m["value_needed"],
                                   "R_if_critical": _r(m["R_if_critical"]), "R_if_ideal": _r(m["R_if_ideal"])}
                                  for m in miss]}
        return self._log("recommend", {"target_level": target_level}, out)

    def get_trace(self, bus: str) -> dict:
        """Return the content of one bus (X, O, M, A, G, R, P, C) of the last run."""
        r = assess(self.cfg, self.sheet, n=self.mc)
        recs = [t for t in r.trace.records if t["bus"] == bus]
        if not recs:
            return self._log("get_trace", {"bus": bus}, {"error": f"no bus {bus}"})
        payload = json.loads(json.dumps(recs[-1]["payload"], default=lambda o: str(o)))
        return self._log("get_trace", {"bus": bus}, {"bus": bus, "block": recs[-1]["block"], "payload": payload})

    # ---------------------------------------------------------------- schemas
    TOOL_SPECS = {
        "load_state": ("Load one of the input states E1..E5 (current, degraded, improved, critical, ideal).",
                       {"state": {"type": "string", "enum": ["E1", "E2", "E3", "E4", "E5"]}}, ["state"]),
        "assess_current": ("Run the seven-stage assessment on the current sheet; returns R, level, R_min, "
                           "enclosure, goal profile, action scores and weight-robustness shares.", {}, []),
        "explain_action": ("Explain one basic action at bus level (values, class tables, normalized "
                           "scores, cap, veto).", {"action": {"type": "string"}}, ["action"]),
        "what_if": ("Change one measurement (null = not reported) and compare the verdict before/after.",
                    {"action": {"type": "string"}, "metric": {"type": "string"},
                     "value": {"type": ["number", "null"]}}, ["action", "metric", "value"]),
        "recommend": ("Greedy improvement plan to reach a target level with a stable verdict.",
                      {"target_level": {"type": ["string", "null"], "enum": ["C", "BA", "A", "AA", "H", None]}},
                      ["target_level"]),
        "get_trace": ("Return the content of one bus of the last run.",
                      {"bus": {"type": "string", "enum": ["X", "O", "M", "A", "G", "R", "P", "C"]}}, ["bus"]),
    }

    def schemas(self) -> list[dict]:
        """JSON-schema tool definitions (Claude tool-use format)."""
        return [{"name": n, "description": d,
                 "input_schema": {"type": "object", "properties": p, "required": req,
                                  "additionalProperties": False}}
                for n, (d, p, req) in self.TOOL_SPECS.items()]

    def dispatch(self, name: str, args: dict) -> Any:
        if name not in self.TOOL_SPECS:
            return {"error": f"unknown tool {name}"}
        return getattr(self, name)(**args)


class ClaudeAnalyst:
    """Analyst agent on the Claude API using the SDK tool runner.

    Requires `pip install anthropic` and credentials (ANTHROPIC_API_KEY or an
    `ant auth login` profile). Server-side refusal fallbacks are enabled.
    """

    def __init__(self, toolbox: ResilienceToolbox, model: str = DEFAULT_MODEL, effort: str = "high"):
        import anthropic
        from anthropic import beta_tool

        self.tb = toolbox
        self.model, self.effort = model, effort
        self.client = anthropic.Anthropic()
        tb = toolbox

        @beta_tool
        def load_state(state: str) -> str:
            """Load one of the input states E1..E5 (current, degraded, improved, critical, ideal).

            Args:
                state: E1, E2, E3, E4 or E5.
            """
            return json.dumps(tb.load_state(state))

        @beta_tool
        def assess_current() -> str:
            """Run the seven-stage assessment on the current sheet and return the structured verdict."""
            return json.dumps(tb.assess_current())

        @beta_tool
        def explain_action(action: str) -> str:
            """Explain one basic action at bus level (values, class tables, scores, cap, veto).

            Args:
                action: code of the basic action, e.g. UN.S1.A1.
            """
            return json.dumps(tb.explain_action(action))

        @beta_tool
        def what_if(action: str, metric: str, value: float | None) -> str:
            """Change one measurement (null = not reported) and compare the verdict before and after.

            Args:
                action: code of the basic action, e.g. CN.S1.A1.
                metric: metric code inside the action, e.g. AM-DA-1.
                value: new physical value, or null for not reported.
            """
            return json.dumps(tb.what_if(action, metric, value))

        @beta_tool
        def recommend(target_level: str | None = None) -> str:
            """Greedy improvement plan to reach a target level (C, BA, A, AA, H) with a stable verdict.

            Args:
                target_level: target level code; null = next level.
            """
            return json.dumps(tb.recommend(target_level))

        @beta_tool
        def get_trace(bus: str) -> str:
            """Return the content of one bus (X, O, M, A, G, R, P, C) of the last run.

            Args:
                bus: bus name.
            """
            return json.dumps(tb.get_trace(bus))

        self.tools = [load_state, assess_current, explain_action, what_if, recommend, get_trace]

    def ask(self, question: str, max_iterations: int = 12) -> str:
        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_iterations=max_iterations,
            messages=[{"role": "user", "content": question}],
        )
        final = runner.until_done()
        if final.stop_reason == "refusal":
            return "[the request was declined by the model]"
        return "".join(b.text for b in final.content if b.type == "text")


class OfflineAnalyst:
    """Deterministic analyst: same tools, templated report (no network)."""

    def __init__(self, toolbox: ResilienceToolbox, lang: str = "ua"):
        self.tb = toolbox
        self.lang = lang

    def report(self, state: str | None = None) -> str:
        tb = self.tb
        if state:
            tb.load_state(state)
        v = tb.assess_current()
        if "failure_code" in v:
            return f"Оцінювання зупинено: {v['failure_code']} — {v['detail']}"
        rec = tb.recommend()
        weak = tb.explain_action(v["weakest_action"])
        ua = self.lang == "ua"
        L, U = v["enclosure"]
        shares = ", ".join(f"{k} {s:.1%}" for k, s in v["robustness"]["level_shares"].items())
        lname = lv.name(lv.LEVEL_CODES.index(v["level"]) + 1, "ua" if ua else "en")
        lines = []
        if ua:
            lines.append(f"## Вердикт: R = {v['R']:.3f} — рівень «{lname}» ({v['level']})")
            lines.append(f"- Найслабша ланка R_min = {v['R_min']:.3f} ({v['level_min']}), дія {v['weakest_action']}; "
                         f"найслабша ціль — {v['weakest_goal']}.")
            lines.append(f"- Оболонка через пропущені дані: [{L:.3f}, {U:.3f}] — "
                         + ("вердикт стабільний." if v["stable_wrt_missing_data"]
                            else "перетинає межу рівнів, вердикт НЕ стабільний."))
            lines.append(f"- Чутливість до ваг (Dirichlet ρ={v['robustness']['rho']}): {shares}.")
            if v["vetoed_actions"]:
                lines.append(f"- ВЕТО: втрачено ключову спроможність у {', '.join(v['vetoed_actions'])}.")
            lines.append(f"\n### Чому {weak['action']} найслабша")
            low = sorted([m for m in weak["metrics"] if m["m"] is not None], key=lambda m: m["m"])[:3]
            for m in low:
                lines.append(f"- {m['metric']} {m['name']}: x = {m['x']} {m['unit']} → m = {m['m']:.3f} ({m['level']})")
            lines.append(f"\n### План покращення до рівня {rec['target_level']}"
                         + (" (досягається)" if rec["reached"] else " (не досягнуто в межах кроків)"))
            for s in rec["steps"][1:]:
                lines.append(f"{s['step']}. {s['measurement']} → {s['to']}: R = {s['R']:.3f}, R_L = {s['R_L']:.3f}")
            for m in rec["missing_values"]:
                lines.append(f"- Пропущений показник {m['metric']}: за його звітування R ∈ "
                             f"[{m['R_if_critical']:.3f}, {m['R_if_ideal']:.3f}]; для рівня {rec['target_level']} "
                             f"потрібне значення ≥ {m['value_needed']}.")
            lines.append("\n_Дані сценарію ілюстративні; результат верифікує реалізацію, а не польову валідність._")
        else:
            lines.append(f"## Verdict: R = {v['R']:.3f} — level '{lname}' ({v['level']})")
            lines.append(f"- Weakest link R_min = {v['R_min']:.3f} in {v['weakest_action']}; weakest goal {v['weakest_goal']}.")
            lines.append(f"- Missing-data enclosure [{L:.3f}, {U:.3f}] — "
                         + ("stable." if v["stable_wrt_missing_data"] else "crosses a level boundary (not stable)."))
            lines.append(f"- Weight robustness: {shares}.")
            for s in rec["steps"][1:]:
                lines.append(f"{s['step']}. improve {s['measurement']} -> {s['to']}: R = {s['R']:.3f}")
        return "\n".join(lines)
