"""Discrete-event model of an agentic SOC with an evidence-bound action-warrant
gateway (EBAW) and baseline admission policies.

Common random numbers: every proposal stream is generated once per
(scenario, replication) seed and replayed against every policy, so policy
comparisons are paired.  Queueing (orchestrator workers, analysts) evolves
per policy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import simpy

from .model import (ACTIONS, ACTION_NAMES, ACTION_P, TIERS, TAU_SIGMA, T_WAIT, PREDICATES)

T_WAIT_MIN = 5.0      # minimum confirmation wait of the gateway (s)
T_WAIT_MAX = 600.0    # absolute cap on the budget-aware confirmation wait (s)

INF = math.inf


@dataclass(frozen=True)
class Policy:
    name: str
    kind: str                 # "AD" agent-direct, "CO" confidence-only, "RO" receipt-only, "GW" gateway
    S: frozenset = frozenset()
    reval: bool = False
    tiered: tuple = ()        # optional ((tier, frozenset), ...) overriding S per risk tier
    edf: bool = True          # expiry-ordered (earliest-deadline-first) dispatch of warrants

    def preds(self, tier):
        for t, S in self.tiered:
            if t == tier:
                return S
        return self.S


MAIN_POLICIES = [
    Policy("Agent-direct (no gate)", "AD"),
    Policy("Confidence-only", "CO"),
    Policy("Receipt-only", "RO"),
    Policy("Gateway, no revalidation", "GW", frozenset(PREDICATES), False),
    Policy("EBAW gateway (full)", "GW", frozenset(PREDICATES), True),
    Policy("EBAW gateway (tier-scoped)", "GW", frozenset(PREDICATES), True,
           (("low", frozenset("CLV")), ("medium", frozenset("CLV")))),
]
SHORT = {"Agent-direct (no gate)": "AD", "Confidence-only": "CO", "Receipt-only": "RO",
         "Gateway, no revalidation": "GN", "EBAW gateway (full)": "EB",
         "EBAW gateway (tier-scoped)": "ET"}


def lattice_policies():
    out = []
    for k in range(len(PREDICATES) + 1):
        for comb in combinations(PREDICATES, k):
            S = frozenset(comb)
            label = "".join(x for x in PREDICATES if x in S) or "∅"
            out.append(Policy("GW{" + label + "}", "GW", S, True))
    return out


class Prop:
    __slots__ = ("pid", "kind", "y", "action", "tier", "Phi", "D", "tau", "tau_hat", "t_obs", "t_avail",
                 "t_prop", "t_conf", "dq", "dg", "dc", "prep", "analyst_time", "analyst_correct", "refresh",
                 "lc2", "ds", "t_ret", "t_drift", "t_pc1", "f1", "t_pc2", "f2", "s", "c_gw", "c_att",
                 "c_true", "ref_ok", "rcpt", "urgent_hint")


def _lognorm(rng, median, sigma, size=None):
    return median * np.exp(sigma * rng.standard_normal(size))


def generate(params: dict, seed: int, cal) -> list:
    """Generate the proposal stream for one replication (policy independent).

    Synchronised common random numbers: every proposal draws its attributes from its
    own generator seeded by (seed, stream, index) with a fixed number of draws, so a
    change of one scenario parameter does not shift the attributes of other proposals.
    Base arrivals are identical across scenarios for the same replication seed.
    """
    H = params["horizon"]
    lam = params["rate_per_h"] / 3600.0
    lam_rel = params["pol_rate_rel_per_h"] / 3600.0
    cumA = np.cumsum(ACTION_P)
    props = []

    def lc_mix(ua, ub, z):
        if ua < params["lc_stall_p"]:
            return params["lc_stall_lo"] + (params["lc_stall_hi"] - params["lc_stall_lo"]) * ub
        if ua < params["lc_stall_p"] + params["lc_delay_p"]:
            return params["lc_delay_lo"] + (params["lc_delay_hi"] - params["lc_delay_lo"]) * ub
        return params["lc_median"] * math.exp(params["lc_sigma"] * z)

    def common(p, u, z, ex):
        a = ACTIONS[p.action]
        p.tier, p.Phi, p.D = a["tier"], a["Phi"], a["D"]
        p.tau = a["tau"] * math.exp(TAU_SIGMA * z[3])
        p.tau_hat = a["tau"] * math.exp(1.2816 * TAU_SIGMA)          # p90 estimate
        sg = params["lat_sigma"]
        p.dq = params["dq_median"] * math.exp(sg * z[4])
        p.dg = params["dg_median"] * math.exp(sg * z[5])
        p.dc = params["dc_median"] * math.exp(sg * z[6])
        p.prep = params["prep_median"] * math.exp(params["prep_sigma"] * z[7])
        p.analyst_time = params["analyst_median"] * math.exp(params["analyst_sigma"] * z[8])
        p.analyst_correct = bool(u[7] < params["analyst_acc"])
        p.refresh = params["refresh_median"] * math.exp(params["refresh_sigma"] * z[9])
        p.lc2 = lc_mix(u[8], u[9], z[10])
        p.ds = params["ds"]
        p.t_pc1 = p.t_prop + (ex[2] / lam_rel if lam_rel > 0 else INF)
        p.t_pc2 = p.t_pc1 + (ex[3] / lam_rel if lam_rel > 0 else INF)
        p.f1 = bool(u[10] < params["p_forbid"])
        p.f2 = bool(u[11] < params["p_forbid"])
        p.urgent_hint = False

    def draws(key):
        g = np.random.default_rng(key)
        return g.random(16), g.standard_normal(14), g.exponential(1.0, 6), g.beta(*params["mal_beta"]), \
            g.beta(*params["ben_beta"])

    def genuine(t, key):
        u, z, ex, bm, bb = draws(key)
        p = Prop()
        p.kind = "gen"
        p.y = int(u[0] < params["p_mal"])
        p.action = ACTION_NAMES[int(min(np.searchsorted(cumA, u[1]), len(cumA) - 1))]
        p.t_obs = float(t)
        ing = params["ing_median"] * math.exp(params["ing_sigma"] * z[0])
        if u[2] < params["stale_p"]:
            ing += params["stale_lo"] + (params["stale_hi"] - params["stale_lo"]) * u[3]
        p.t_avail = p.t_obs + ing
        p.t_prop = p.t_avail + params["agent_median"] * math.exp(params["agent_sigma"] * z[1])
        p.t_conf = p.t_avail + params["ds"] + lc_mix(u[4], u[5], z[2])
        p.s = float(bm if p.y == 1 else bb)
        p.c_gw = float(cal(p.s))
        p.c_att = p.c_gw
        p.c_true = p.c_gw
        p.ref_ok = "ok"
        p.rcpt = True
        p.t_ret = p.t_obs + params["ret_mean"] * ex[0] if (p.y == 0 and u[6] < params["ret_p_benign"]) else INF
        p.t_drift = p.t_obs + ACTIONS[p.action]["drift"] * ex[1] if p.y == 1 else INF
        common(p, u, z, ex)
        return p

    g = np.random.default_rng([seed, 100])
    base_t = np.sort(g.uniform(0, H, g.poisson(lam * H)))
    base = [genuine(t, [seed, 1, i]) for i, t in enumerate(base_t)]
    props.extend(base)
    for k, (a, b) in enumerate(params["surge"]):
        g = np.random.default_rng([seed, 200 + k])
        st = np.sort(g.uniform(a, b, g.poisson(lam * (params["surge_mult"] - 1.0) * (b - a))))
        props.extend(genuine(t, [seed, 2 + k, i]) for i, t in enumerate(st))

    for j, (kind, frac) in enumerate((("hal", params["adv_halluc"]), ("inj", params["adv_inject"]),
                                      ("tam", params["adv_tamper"]))):
        g = np.random.default_rng([seed, 300 + j])
        at = np.sort(g.uniform(60.0, H, g.poisson(lam * frac * H)))
        for i, t in enumerate(at):
            u, z, ex, _, _ = draws([seed, 400 + j, i])
            p = Prop()
            p.kind = kind
            p.y = -1
            p.t_prop = float(t)
            p.t_ret, p.t_drift = INF, INF
            p.s = float("nan")
            p.c_gw, p.c_true = 0.0, 0.0
            if kind == "hal":
                # cites a real, already confirmed record of another asset
                earlier = [q for q in base if q.t_conf < t] or base[:1]
                ref = earlier[int(u[12] * len(earlier)) % len(earlier)]
                p.action = ACTION_NAMES[int(min(np.searchsorted(cumA, u[1]), len(cumA) - 1))]
                p.c_att = ref.c_gw
                p.t_obs = min(ref.t_obs, t - 5.0)
                p.t_conf = ref.t_conf
                p.ref_ok, p.rcpt = "mismatch", True
            elif kind == "inj":
                p.action = ["disable_account", "isolate_server", "block_ip"][int(u[1] * 3) % 3]
                p.c_att = 0.99
                p.t_obs = t - 15.0
                real = bool(u[12] < 0.5)
                p.t_conf = t - 30.0 if real else INF
                p.ref_ok, p.rcpt = ("mismatch", True) if real else ("none", False)
            else:  # tampered off-chain analytics record (forged score, anchor mismatch)
                p.action = ["isolate_host", "disable_account", "isolate_server", "kill_process"][int(u[1] * 4) % 4]
                p.c_att = 0.99
                p.c_gw = 0.99          # forged off-chain estimate read by a gateway without ledger check
                p.t_obs = t - 15.0
                real = bool(u[12] < 0.5)
                p.t_conf = t - 30.0 if real else INF
                p.ref_ok, p.rcpt = "forged", real
            p.t_avail = p.t_obs
            common(p, u, z, ex)
            props.append(p)

    props.sort(key=lambda q: q.t_prop)
    for i, p in enumerate(props):
        p.pid = i
    return props


# ----------------------------------------------------------------------------------------------
# helpers on the ground-truth state
def version(p, t):
    return 0 if t < p.t_pc1 else (1 if t < p.t_pc2 else 2)


def permitted(p, t):
    v = version(p, t)
    return True if v == 0 else (not p.f1 if v == 1 else not p.f2)


def retracted(p, t):
    return t >= p.t_ret


def drifted(p, t):
    return t >= p.t_drift


class Ctx:
    def __init__(self, env, params):
        self.env = env
        self.params = params
        self.orch = simpy.PriorityResource(env, capacity=params["n_orch"])
        self.analysts = simpy.PriorityResource(env, capacity=params["n_analyst"])
        self.waits = []

    def orch_estimate(self):
        """p90 of recent orchestration delay (queue wait + prep) used by the deadline predicate."""
        prep90 = self.params["prep_median"] * math.exp(1.2816 * self.params["prep_sigma"])
        if len(self.waits) < 5:
            return prep90
        w = np.percentile(self.waits[-50:], 90)
        return float(w + prep90)


def new_record(p):
    return dict(pid=p.pid, kind=p.kind, y=p.y, action=p.action, tier=p.tier, t_obs=p.t_obs, t_prop=p.t_prop,
                outcome=None, executed=False, manual=False, unsafe=False, violation=False, viol_set="",
                escalated=False, urgent=False, t_done=INF, t_x=INF, t_chk=INF, t_reval=INF, t_iss=INF,
                t_disp=INF, t_decided=INF, t_closed=INF, reverified=0, reissued=0,
                fails_first="", fails_reval="", fails_all=set(), window=float("nan"),
                window_change=False, window_change_v=False, lc_timeout=False)


def eval_preds(p, t, S, tobs_eff, t_conf_eff, ctx, stage, v_issue=0):
    """Evaluate the predicates in S at time t. Returns (failset, info)."""
    fails, info = set(), {}
    if "L" in S:
        if p.ref_ok != "ok":
            fails.add("L"); info["L"] = "invalid"
        elif t < t_conf_eff:
            fails.add("L"); info["L"] = "pending"
        elif retracted(p, t):
            fails.add("L"); info["L"] = "retracted"
    if "C" in S:
        c = 0.0 if retracted(p, t) else p.c_gw
        ta, to = TIERS[p.tier]
        if c < ta:
            fails.add("C"); info["C"] = "verify" if c >= to else "observe"
    if "F" in S and (t - tobs_eff) > p.Phi:
        fails.add("F")
    if "V" in S and stage == "reval" and version(p, t) != v_issue:
        fails.add("V")
    if "D" in S:
        horizon = p.dg + p.dc + p.tau_hat + (ctx.orch_estimate() if stage == "issue" else 0.0)
        if t + horizon > p.t_obs + p.D:
            fails.add("D")
    return fails, info


def assess(p, r, t_x, tobs_eff, t_conf_eff, v_ref, manual):
    """Oracle evaluation at the execution instant."""
    unsafe = (p.kind != "gen") or (p.y == 0) or retracted(p, t_x) or (not permitted(p, t_x)) or drifted(p, t_x)
    r["executed"] = True
    r["manual"] = manual
    r["unsafe"] = bool(unsafe)
    r["t_x"] = t_x
    if not manual:
        ta, _ = TIERS[p.tier]
        c_true = 0.0 if (p.kind != "gen" or retracted(p, t_x)) else p.c_true
        v = []
        if (t_x - tobs_eff) > p.Phi: v.append("F")
        if c_true < ta: v.append("C")
        if not (p.ref_ok == "ok" and t_x >= t_conf_eff and not retracted(p, t_x)): v.append("L")
        if version(p, t_x) != v_ref or not permitted(p, t_x): v.append("V")
        if t_x + p.tau > p.t_obs + p.D: v.append("D")
        r["violation"] = bool(v)
        r["viol_set"] = "".join(v)


# ----------------------------------------------------------------------------------------------
def run(params: dict, props: list, policy: Policy):
    env = simpy.Environment()
    ctx = Ctx(env, params)
    ctx.reval = bool(policy.kind == "GW" and policy.reval)
    R = [new_record(p) for p in props]
    for p in props:
        env.process(_proposal(env, p, R[p.pid], ctx, policy))
    env.run()
    return R


def _proposal(env, p, r, ctx, pol):
    yield env.timeout(p.t_prop)
    if pol.kind == "AD":
        r["t_decided"] = env.now
        yield from _execute(env, p, r, ctx, pol, p.t_obs, p.t_conf, version(p, env.now), INF)
    elif pol.kind == "CO":
        yield from _confidence_only(env, p, r, ctx, pol)
    elif pol.kind == "RO":
        yield from _receipt_only(env, p, r, ctx, pol)
    else:
        yield from _gateway(env, p, r, ctx, pol)


def _close(env, r, outcome):
    r["outcome"] = outcome
    r["t_closed"] = env.now
    if r["t_decided"] == INF:
        r["t_decided"] = env.now


def _confidence_only(env, p, r, ctx, pol):
    if not permitted(p, env.now):
        _close(env, r, "rejected_policy"); return
    ta, to = TIERS[p.tier]
    r["t_chk"] = env.now
    if p.c_att >= ta:
        r["t_decided"] = env.now
        yield from _execute(env, p, r, ctx, pol, p.t_obs, p.t_conf, version(p, env.now), env.now)
    elif p.c_att >= to:
        r["t_decided"] = env.now
        env.process(_escalate(env, p, r, ctx, urgent=False))
    else:
        _close(env, r, "no_action_observe")


def _receipt_only(env, p, r, ctx, pol):
    if not permitted(p, env.now):
        _close(env, r, "rejected_policy"); return
    if not p.rcpt:
        yield env.timeout(p.dq)
        _close(env, r, "rejected_no_receipt"); return
    if env.now < p.t_conf:
        wait = p.t_conf - env.now
        if wait > T_WAIT:
            yield env.timeout(T_WAIT)
            r["lc_timeout"] = True
            r["t_decided"] = env.now
            env.process(_escalate(env, p, r, ctx, urgent=False)); return
        yield env.timeout(wait)
    yield env.timeout(p.dq)
    r["t_chk"] = env.now
    r["t_decided"] = env.now
    yield from _execute(env, p, r, ctx, pol, p.t_obs, p.t_conf, version(p, env.now), env.now)


def _gateway(env, p, r, ctx, pol):
    S = pol.preds(p.tier)
    tobs_eff, t_conf_eff = p.t_obs, p.t_conf
    reverified = False
    while True:
        if "L" in S and p.ref_ok == "ok" and env.now < t_conf_eff:
            # budget-aware confirmation wait (Proposition 1): wait only while the action can
            # still be admitted, i.e. while the projected slack remains non-negative
            need = p.dq + p.dg + ctx.orch_estimate() + p.dg + p.dc
            bounds = [T_WAIT_MAX + env.now]
            if "F" in S:
                bounds.append(tobs_eff + p.Phi - need)
            if "D" in S:
                bounds.append(p.t_obs + p.D - p.tau_hat - need)
            t_wait_max = min(bounds)
            if t_wait_max > env.now:
                if t_conf_eff <= t_wait_max:
                    yield env.timeout(t_conf_eff - env.now)
                else:
                    yield env.timeout(t_wait_max - env.now)
                    r["lc_timeout"] = True            # slack exhausted before confirmation
        if "L" in S:
            yield env.timeout(p.dq)
        t = env.now
        r["t_chk"] = t
        fails, info = eval_preds(p, t, S, tobs_eff, t_conf_eff, ctx, "issue")
        r["fails_all"] |= fails
        if r["fails_first"] == "" and not reverified:
            r["fails_first"] = "".join(x for x in "FCLVD" if x in fails) or "-"
        if not permitted(p, t):
            yield env.timeout(p.dg)
            _close(env, r, "rejected_policy"); return
        if not fails:
            yield env.timeout(p.dg)                       # evaluate + sign the warrant
            r["t_iss"] = env.now
            r["t_decided"] = env.now
            v_issue = version(p, env.now)
            res = yield from _execute(env, p, r, ctx, pol, tobs_eff, t_conf_eff, v_issue, t, reverified=reverified)
            if res == "reverify":
                if reverified:
                    env.process(_escalate(env, p, r, ctx, urgent=False)); return
                out = yield from _reverify(env, p, r)
                if out is None:
                    return
                tobs_eff, t_conf_eff = out
                reverified = True
                continue
            return
        # failure handling (deterministic precedence)
        yield env.timeout(p.dg)
        r["t_decided"] = env.now
        if "L" in fails and info.get("L") == "invalid":
            _close(env, r, "rejected_invalid_evidence"); return
        if "L" in fails and info.get("L") == "retracted":
            _close(env, r, "rejected_retracted"); return
        if "C" in fails:
            if info["C"] == "verify":
                env.process(_escalate(env, p, r, ctx, urgent=False))
            else:
                _close(env, r, "no_action_observe")
            return
        if "D" in fails:
            env.process(_escalate(env, p, r, ctx, urgent=True)); return
        if "F" in fails:
            if reverified:
                env.process(_escalate(env, p, r, ctx, urgent=False)); return
            out = yield from _reverify(env, p, r)
            if out is None:
                return
            tobs_eff, t_conf_eff = out
            reverified = True
            continue
        # evidence still unconfirmed when the admissible waiting window closed
        r["lc_timeout"] = True
        env.process(_escalate(env, p, r, ctx, urgent=False)); return


def _reverify(env, p, r):
    """Fresh, target-bound sensor query plus anchoring of the new observation."""
    r["reverified"] += 1
    yield env.timeout(p.refresh)
    if p.kind != "gen" or drifted(p, env.now) or retracted(p, env.now):
        _close(env, r, "rejected_state_changed")
        return None
    return env.now, env.now + p.ds + p.lc2


def _execute(env, p, r, ctx, pol, tobs_eff, t_conf_eff, v_ref, t_chk, reverified=False, prio=1):
    t_q = env.now
    S = pol.preds(p.tier)
    if pol.kind == "GW" and pol.edf:
        # expiry-ordered (earliest-deadline-first) dispatch of warrants.  The dispatch key is the
        # warrant expiry of Equation (9), computed for every warrant, including tiers whose contract
        # does not enforce P1 or P5, so that the order never depends on which predicates are checked.
        t_exp = min(tobs_eff + p.Phi, p.t_obs + p.D - p.tau_hat)
        prio = 1.0 + t_exp
        r["t_exp"] = t_exp
    req = ctx.orch.request(priority=prio)
    yield req
    r["t_disp"] = env.now
    ctx.waits.append(env.now - t_q)
    yield env.timeout(p.prep)
    if pol.kind == "GW" and pol.reval:
        refreshed = False
        while True:
            t_ready = env.now
            fails, info = eval_preds(p, t_ready, S, tobs_eff, t_conf_eff, ctx, "reval", v_ref)
            yield env.timeout(p.dg)                      # revalidation evaluation (delta_r)
            r["t_reval"] = env.now
            if not fails:
                break
            r["fails_all"] |= fails
            r["fails_reval"] += "".join(x for x in "FCLVD" if x in fails)
            if ("L" in fails and info.get("L") in ("retracted", "invalid")) or "C" in fails:
                ctx.orch.release(req); _close(env, r, "rejected_retracted"); return "done"
            if "V" in fails:
                if not permitted(p, env.now):
                    ctx.orch.release(req); _close(env, r, "rejected_policy"); return "done"
                yield env.timeout(p.dg)                  # re-issue under the current version
                v_ref = version(p, env.now)
                r["reissued"] += 1
                fails.discard("V")
            if "D" in fails:
                ctx.orch.release(req)
                env.process(_escalate(env, p, r, ctx, urgent=True)); return "done"
            if "F" in fails or ("L" in fails and info.get("L") == "pending"):
                if refreshed:
                    ctx.orch.release(req)
                    env.process(_escalate(env, p, r, ctx, urgent=False)); return "done"
                # pre-execution freshness refresh while the worker is held
                out = yield from _reverify(env, p, r)
                if out is None:
                    ctx.orch.release(req); return "done"
                tobs_eff, t_conf_eff = out
                wait = t_conf_eff - env.now
                if wait > T_WAIT:
                    yield env.timeout(T_WAIT)
                    r["lc_timeout"] = True
                    ctx.orch.release(req)
                    env.process(_escalate(env, p, r, ctx, urgent=False)); return "done"
                yield env.timeout(max(0.0, wait) + p.dq)
                refreshed = True
                continue
            if not fails:
                break
        t_last = env.now
        yield env.timeout(p.dc)                          # commit of the EXECUTE verdict (residual window)
    else:
        t_last = t_chk if t_chk != INF else r["t_decided"]
    t_x = env.now
    r["window"] = t_x - t_last
    r["window_change"] = bool(version(p, t_x) != version(p, t_last) or (t_last < p.t_ret <= t_x)
                              or (t_last < p.t_drift <= t_x))
    r["window_change_v"] = bool(version(p, t_x) != version(p, t_last))
    assess(p, r, t_x, tobs_eff, t_conf_eff, v_ref, manual=False)
    yield env.timeout(p.tau)
    ctx.orch.release(req)
    r["t_done"] = env.now
    _close(env, r, "executed_auto")
    return "done"


def _escalate(env, p, r, ctx, urgent):
    r["escalated"] = True
    r["urgent"] = urgent
    with ctx.analysts.request(priority=0 if urgent else 1) as req:
        yield req
        yield env.timeout(p.analyst_time)
    t = env.now
    truth = (p.kind == "gen" and p.y == 1 and not drifted(p, t))
    approve = truth if p.analyst_correct else (not truth)
    if not approve or not permitted(p, t):
        _close(env, r, "analyst_declined"); return
    v_ref = version(p, t)
    with ctx.orch.request(priority=0) as req:
        yield req
        yield env.timeout(p.prep)
        if ctx.reval:
            # human-attested warrant: the attestation replaces P1, P2 and P5; evidence retraction
            # and the policy version are revalidated before execution
            yield env.timeout(p.dg)
            tr = env.now
            if retracted(p, tr):
                _close(env, r, "rejected_retracted"); return
            if version(p, tr) != v_ref:
                if not permitted(p, tr):
                    _close(env, r, "rejected_policy"); return
                yield env.timeout(p.dg)
                v_ref = version(p, env.now)
                r["reissued"] += 1
            yield env.timeout(p.dc)
        t_x = env.now
        assess(p, r, t_x, t, t, v_ref, manual=True)
        yield env.timeout(p.tau)
    r["t_done"] = env.now
    _close(env, r, "executed_manual")


# ----------------------------------------------------------------------------------------------
def summarize(R, props, costs=(10.0, 5.0, 1.0)):
    n = len(R)
    gen_mal = [r for r in R if r["kind"] == "gen" and r["y"] == 1]
    adv = [r for r in R if r["kind"] != "gen"]
    auto = [r for r in R if r["executed"] and not r["manual"]]
    unsafe = sum(r["unsafe"] for r in R if r["executed"])
    viol = sum(r["violation"] for r in auto)
    esc = sum(r["escalated"] for r in R)
    D = {r["pid"]: props[r["pid"]].D for r in gen_mal}
    ttc = []
    miss = 0
    for r in gen_mal:
        ok = r["executed"] and not r["unsafe"] and (r["t_done"] - r["t_obs"]) <= D[r["pid"]]
        if r["executed"] and not r["unsafe"]:
            ttc.append(r["t_done"] - r["t_obs"])
        miss += (not ok)
    adv_exec = sum(r["executed"] for r in adv)
    U = unsafe / n
    M = miss / n
    E = esc / n
    return dict(n=n, n_mal=len(gen_mal), n_adv=len(adv), n_auto=len(auto), unsafe=unsafe, viol=viol, esc=esc,
                miss=miss, adv_exec=adv_exec,
                UER=1000.0 * U, CVR=100.0 * viol / max(1, len(auto)), DMR=100.0 * miss / max(1, len(gen_mal)),
                ESC=100.0 * E, TTC_med=float(np.median(ttc)) if ttc else float("nan"),
                TTC_p95=float(np.percentile(ttc, 95)) if ttc else float("nan"),
                J=costs[0] * U + costs[1] * M + costs[2] * E)
