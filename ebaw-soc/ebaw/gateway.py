"""Deterministic EBAW gateway core (Algorithm 1) and enforcement point.

This module is the reference implementation of the admission logic outside the
discrete-event simulator (``ebaw.sim``): it evaluates the five-predicate contract from
authenticated inputs only (signed observations, quorum-read ledger state, the versioned
policy store and the gateway clock), issues signed single-use expiring warrants,
revalidates them before execution and lets enforcement points verify and consume them.
It holds no state except the nonce store and the commit log, and every timeout, parse
error or missing input evaluates the affected predicate to false (assumption A4).

The caller drives time: ``admit`` may answer ``WAIT`` (evidence pending, still within the
budget-aware wait of Eq. 10) or ``REFRESH`` (stale evidence), and the caller retries.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .ledger import QuorumLedger
from .model import ACTIONS, PREDICATES, TAU_SIGMA, TIERS
from .warrant import (NonceStore, Signer, Verifier, Warrant, canonical, decode, encode, make_nonce, make_wid,
                      merkle_root, sha256_hex)

Z90 = 1.2816


# ----------------------------------------------------------------------------------------------
# authenticated inputs
@dataclass
class Evidence:
    """Off-chain analytical record e = <H(raw), x, t_obs, s, src> with the sensor signature
    over the raw-event digest and the ledger transaction that anchors H(e)."""
    evidence_id: str
    asset: str
    t_obs: float
    score: float
    raw_digest: str
    sensor: str
    sensor_sig: str
    tx_id: str | None

    def digest(self) -> str:
        return sha256_hex(canonical(dict(raw=self.raw_digest, asset=self.asset, t_obs=self.t_obs,
                                         score=self.score, src=self.sensor)))


@dataclass
class Proposal:
    """pi = (alpha, x, epsilon, c_hat, t_p).  ``claimed_conf`` is recorded but never used."""
    pid: str
    action: str
    target: str
    evidence_refs: list
    claimed_conf: float
    t_prop: float


@dataclass
class PolicyStore:
    """Versioned policy partitions (alpha, asset).  Each partition holds a list of
    (t_change, permit) entries; version v is the number of changes up to t."""
    changes: dict = field(default_factory=dict)

    def partition(self, action: str, asset: str) -> str:
        return f"{action}:{asset}"

    def add_change(self, part: str, t: float, permit: bool):
        self.changes.setdefault(part, []).append((t, permit))
        self.changes[part].sort()

    def version(self, part: str, t: float) -> int:
        return sum(1 for tc, _ in self.changes.get(part, []) if tc <= t)

    def permitted(self, part: str, t: float) -> bool:
        v = self.version(part, t)
        return True if v == 0 else self.changes[part][v - 1][1]


@dataclass
class Decision:
    verdict: str                 # ISSUE, WAIT, REFRESH, REJECT, ESCALATE, ESCALATE_URGENT, MONITOR,
    t: float                     # EXECUTE, REISSUE, REFUSE
    fails: str = ""
    reason: str = ""
    pred: dict = field(default_factory=dict)
    token: str | None = None
    t_wait_max: float | None = None


# ----------------------------------------------------------------------------------------------
class Gateway:
    def __init__(self, signer: Signer, ledger: QuorumLedger, policies: PolicyStore, calibrator,
                 sensor_keys: dict, contract=frozenset(PREDICATES), actions=ACTIONS, tiers=TIERS,
                 dq=0.08, dg=0.035, dc=0.02, prep90=None, t_wait_cap=600.0):
        self.signer, self.ledger, self.policies, self.cal = signer, ledger, policies, calibrator
        self.sensor_keys = sensor_keys            # sensor name -> Verifier
        self.S = frozenset(contract)
        self.actions, self.tiers = actions, tiers
        self.dq, self.dg, self.dc = dq, dg, dc
        self.prep90 = 25.0 * math.exp(Z90 * 0.8) if prep90 is None else prep90
        self.t_wait_cap = t_wait_cap
        self.evidence: dict[str, Evidence] = {}
        self.commits: dict[str, float] = {}       # wid -> commit time of the EXECUTE verdict
        self.issued: dict[str, dict] = {}         # wid -> context needed for revalidation
        self.audit: list[dict] = []

    # ---- helpers
    def tau_hat(self, action):
        return self.actions[action]["tau"] * math.exp(Z90 * TAU_SIGMA)

    def register_evidence(self, e: Evidence):
        self.evidence[e.evidence_id] = e

    def _primary(self, prop: Proposal):
        """Authenticated primary evidence bound to the proposed asset, or None."""
        try:
            e = self.evidence[prop.evidence_refs[0]]
        except Exception:
            return None, "missing"
        v = self.sensor_keys.get(e.sensor)
        if v is None or not v.verify(bytes.fromhex(e.raw_digest), bytes.fromhex(e.sensor_sig)):
            return None, "bad_sensor_signature"
        return e, "ok"

    def _ledger(self, e: Evidence | None, prop: Proposal, t: float):
        """Return 'final' | 'pending' | 'retracted' | 'invalid' for P3."""
        if e is None or e.tx_id is None:
            return "invalid"
        state, digest, asset, _ = self.ledger.quorum_read(e.tx_id, t, asset_hint=prop.target)
        if state == "absent":
            return "invalid"
        if digest != e.digest() or asset != prop.target or e.asset != prop.target:
            return "invalid"                    # forged off-chain record or evidence of another asset
        return state

    def confidence(self, e: Evidence | None, prop: Proposal, lstate: str) -> float:
        """g(s) from the authenticated score of the proposed asset; 0 if none or retracted.
        The confidence claimed by the proposer is never read (assumption A3)."""
        if e is None or e.asset != prop.target or lstate == "retracted":
            return 0.0
        return float(self.cal(e.score))

    def evaluate(self, prop: Proposal, t: float, stage: str, v_ref: int | None = None, orch_est: float | None = None,
                 t_obs_eff: float | None = None, S=None):
        S = self.S if S is None else S
        A = self.actions[prop.action]
        ta, to = self.tiers[A["tier"]]
        e, why = self._primary(prop)
        lstate = self._ledger(e, prop, t)
        g = self.confidence(e, prop, lstate)
        t_obs = (e.t_obs if e else -math.inf) if t_obs_eff is None else t_obs_eff
        part = self.policies.partition(prop.action, prop.target)
        v_now = self.policies.version(part, t)
        orch = (self.prep90 if orch_est is None else orch_est) if stage == "issue" else 0.0
        pred = {
            "P1": ("F" not in S) or (t - t_obs <= A["Phi"]),
            "P2": ("C" not in S) or (g >= ta),
            "P3": ("L" not in S) or (lstate == "final"),
            "P4": ("V" not in S) or (stage == "issue") or (v_ref == v_now),
            "P5": ("D" not in S) or (t + self.dg + self.dc + orch + self.tau_hat(prop.action) <= (e.t_obs if e else -math.inf) + A["D"]),
        }
        info = dict(g=g, regime="AUTO" if g >= ta else ("VERIFY" if g >= to else "OBSERVE"), ledger=lstate,
                    evidence=why, age=t - t_obs, version=v_now, partition=part,
                    permitted=self.policies.permitted(part, t))
        fails = "".join(c for c, k in zip("FCLVD", ("P1", "P2", "P3", "P4", "P5")) if not pred[k])
        return pred, fails, info

    def t_wait_max(self, prop: Proposal, e: Evidence, now: float, orch_est=None):
        A = self.actions[prop.action]
        need = self.dq + 2 * self.dg + (self.prep90 if orch_est is None else orch_est) + self.dc
        bounds = [now + self.t_wait_cap]
        if "F" in self.S:
            bounds.append(e.t_obs + A["Phi"] - need)
        if "D" in self.S:
            bounds.append(e.t_obs + A["D"] - self.tau_hat(prop.action) - need)
        return min(bounds)

    # ---- ADMIT (Algorithm 1, lines 1-11)
    def admit(self, prop: Proposal, t: float, orch_est=None, refreshed=False, t_obs_eff=None) -> Decision:
        pred, fails, info = self.evaluate(prop, t, "issue", orch_est=orch_est, t_obs_eff=t_obs_eff)
        e, _ = self._primary(prop)
        if "L" in self.S and info["ledger"] == "pending":
            tw = self.t_wait_max(prop, e, t, orch_est)
            if t < tw:
                return self._log(prop, Decision("WAIT", t, fails, "evidence pending", pred, t_wait_max=tw))
        if not info["permitted"]:
            return self._log(prop, Decision("REJECT", t, fails, "not permitted by current policy", pred))
        if not fails:
            A = self.actions[prop.action]
            t_obs = e.t_obs if t_obs_eff is None else t_obs_eff
            exp = min(t_obs + A["Phi"], e.t_obs + A["D"] - self.tau_hat(prop.action))
            wid = make_wid(prop.pid, t)
            w = Warrant(wid=wid, act=prop.action, tgt=prop.target,
                        evd=merkle_root([e.digest(), sha256_hex(e.tx_id or "")]),
                        pol={"partition": info["partition"], "version": info["version"]},
                        conf=round(info["g"], 6), tier=A["tier"], regime=info["regime"], iat=t + self.dg, exp=exp,
                        nonce=make_nonce(wid, prop.pid), pred=pred)
            tok = encode(w, self.signer)
            self.issued[wid] = dict(prop=prop, t_obs_eff=t_obs)
            return self._log(prop, Decision("ISSUE", t, "", "all predicates hold", pred, token=tok))
        if "L" in fails and info["ledger"] == "invalid":
            return self._log(prop, Decision("REJECT", t, fails, "invalid or foreign evidence (alert)", pred))
        if "L" in fails and info["ledger"] == "retracted":
            return self._log(prop, Decision("REJECT", t, fails, "evidence retracted", pred))
        if "C" in fails:
            v = "ESCALATE" if info["regime"] == "VERIFY" else "MONITOR"
            return self._log(prop, Decision(v, t, fails, f"confidence regime {info['regime']}", pred))
        if "D" in fails:
            return self._log(prop, Decision("ESCALATE_URGENT", t, fails, "deadline budget exhausted", pred))
        if "F" in fails:
            v = "ESCALATE" if refreshed else "REFRESH"
            return self._log(prop, Decision(v, t, fails, "stale evidence", pred))
        return self._log(prop, Decision("ESCALATE", t, fails, "confirmation not obtained within the wait", pred))

    # ---- REVALIDATE (lines 12-18)
    def revalidate(self, token: str, t: float) -> Decision:
        w = decode(token, self.signer.verifier())
        if w is None or w.wid not in self.issued or w.wid in self.commits:
            return Decision("REFUSE", t, reason="invalid signature, unknown or already committed warrant")
        ctx = self.issued[w.wid]
        prop = ctx["prop"]
        pred, fails, info = self.evaluate(prop, t, "reval", v_ref=w.pol["version"], t_obs_eff=ctx["t_obs_eff"])
        if info["ledger"] in ("retracted", "invalid") or "C" in fails:
            return self._log(prop, Decision("REJECT", t, fails, "evidence retracted or invalid at revalidation", pred))
        if "V" in fails:
            if not info["permitted"]:
                return self._log(prop, Decision("REJECT", t, fails, "superseded policy forbids the action", pred))
            return self._log(prop, Decision("REISSUE", t, fails, "policy version changed; re-issue", pred))
        if "D" in fails:
            return self._log(prop, Decision("ESCALATE_URGENT", t, fails, "deadline budget exhausted", pred))
        if "F" in fails or info["ledger"] == "pending":
            return self._log(prop, Decision("REFRESH", t, fails, "stale or pending evidence", pred))
        if t > w.exp:
            return self._log(prop, Decision("REFUSE", t, "", "warrant expired", pred))
        self.commits[w.wid] = t + self.dg + self.dc
        return self._log(prop, Decision("EXECUTE", t, "", "committed", pred, token=token))

    def reissue(self, token: str, t: float) -> Decision:
        """Re-issue a warrant under the current policy version (Algorithm 1, line 15); the old
        warrant is retired so that it can never be committed."""
        w = decode(token, self.signer.verifier())
        if w is None or w.wid not in self.issued:
            return Decision("REFUSE", t, reason="invalid or unknown warrant")
        ctx = self.issued.pop(w.wid)
        prop = ctx["prop"]
        part = self.policies.partition(prop.action, prop.target)
        if not self.policies.permitted(part, t):
            return self._log(prop, Decision("REJECT", t, "V", "superseded policy forbids the action"))
        wid = make_wid(prop.pid, t, "reissue")
        w2 = Warrant(**{**w.claims(), "wid": wid, "iat": t + self.dg, "nonce": make_nonce(wid, prop.pid),
                        "pol": {"partition": part, "version": self.policies.version(part, t)}})
        self.issued[wid] = ctx
        return self._log(prop, Decision("ISSUE", t, "", "re-issued under the current version",
                                        token=encode(w2, self.signer)))

    def _log(self, prop, d: Decision):
        self.audit.append(dict(pid=prop.pid, t=d.t, verdict=d.verdict, fails=d.fails, reason=d.reason))
        return d


class EnforcementPoint:
    """PEP: executes only with a verifying, unexpired, unused warrant for the named action and
    asset, and a committed EXECUTE verdict (assumption A2)."""

    def __init__(self, verifier: Verifier, gateway: Gateway, nonces: NonceStore | None = None):
        self.verifier, self.gw = verifier, gateway
        self.nonces = nonces or NonceStore()
        self.executed: list[tuple[str, str, str, float]] = []

    def execute(self, token: str, action: str, asset: str, t: float) -> tuple[bool, str]:
        w = decode(token, self.verifier)
        if w is None:
            return False, "signature invalid"
        if (w.act, w.tgt) != (action, asset):
            return False, "warrant does not authorize this action on this asset"
        if t > w.exp:
            return False, "warrant expired"
        if w.wid not in self.gw.commits or self.gw.commits[w.wid] > t:
            return False, "no committed EXECUTE verdict"
        if not self.nonces.consume(w.nonce, t, w.wid):
            return False, "nonce already consumed (replay)"
        self.executed.append((w.wid, action, asset, t))
        return True, "executed"
