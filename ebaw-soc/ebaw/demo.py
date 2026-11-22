"""A small, fully deterministic world for exercising the reference gateway core:
sensors, a 5-validator ledger (f = 1), a policy store, a gateway and an enforcement point.
Used by the tests, the notebook and ``python -m ebaw demo``."""
from __future__ import annotations

from .gateway import EnforcementPoint, Evidence, Gateway, PolicyStore, Proposal
from .ledger import QuorumLedger
from .model import BASE, Calibrator
from .warrant import Signer, sha256_hex


class World:
    def __init__(self, contract="FCLVD", force_hmac=False):
        self.signer = Signer(b"demo-gateway", kid="gw-demo", force_hmac=force_hmac)
        self.sensors = {s: Signer(f"demo-sensor|{s}".encode(), kid=s, force_hmac=force_hmac)
                        for s in ("sysmon", "suricata", "keycloak")}
        self.ledger = QuorumLedger(n=5, f=1)
        self.policies = PolicyStore()
        self.cal = Calibrator(BASE, 42)
        self.gw = Gateway(self.signer, self.ledger, self.policies, self.cal,
                          {k: v.verifier() for k, v in self.sensors.items()}, contract=frozenset(contract))
        self.pep = EnforcementPoint(self.signer.verifier(), self.gw)
        self._k = 0

    def observe(self, asset, t_obs, score, sensor="sysmon", lc=1.0, anchor=True, accept_spread=(0.6, 0.7, 0.8, 1.0, 1.4)):
        """Create a signed observation and anchor its digest; finality at a read quorum of 4
        occurs ``lc`` seconds after submission (0.2 s after the observation)."""
        self._k += 1
        raw = sha256_hex(f"raw|{asset}|{t_obs}|{self._k}")
        e = Evidence(f"E{self._k:04d}", asset, t_obs, score, raw, sensor,
                     self.sensors[sensor].sign(bytes.fromhex(raw)).hex(), None)
        if anchor:
            e.tx_id = f"0xtx{self._k:04d}"
            t_sub = t_obs + 0.2
            self.ledger.anchor(e.tx_id, e.digest(), asset, t_sub, [t_sub + lc * a for a in accept_spread])
        self.gw.register_evidence(e)
        return e

    def propose(self, action, target, refs, claimed=0.5, t=0.0, pid=None):
        self._k += 1
        return Proposal(pid or f"P{self._k:04d}", action, target, list(refs), claimed, t)

    def admit_until_done(self, prop, t, max_steps=50):
        """Drive ADMIT through WAIT steps.  Returns the final decision."""
        for _ in range(max_steps):
            d = self.gw.admit(prop, t)
            if d.verdict != "WAIT":
                return d
            nxt = [a.t_final(self.ledger.q) for a in self.ledger.anchors.values()]
            t = min([x for x in nxt if x > t] + [d.t_wait_max]) + 1e-6
        return d


def walkthrough(verbose=True):
    """Narrated sequence of the protocol of Figure 1 with the attacks of the threat model."""
    W = World()
    log = []

    def say(*a):
        log.append(" ".join(str(x) for x in a))
        if verbose:
            print(*a)

    e = W.observe("ws-0042", t_obs=100.0, score=0.97)
    p = W.propose("isolate_host", "ws-0042", [e.evidence_id], claimed=0.99, t=112.0)
    d = W.gw.admit(p, 112.0)
    say(f"[1] proposal isolate_host(ws-0042) at t=112 s -> {d.verdict}; P1..P5 = {d.pred}")
    tok = d.token
    say("    warrant:", tok[:60] + "...")
    ok, why = W.pep.execute(tok, "isolate_host", "ws-0042", 140.0)
    say(f"[2] PEP before revalidation/commit -> {ok} ({why})")
    r = W.gw.revalidate(tok, 140.0)
    say(f"[3] revalidation at t=140 s -> {r.verdict}")
    ok, why = W.pep.execute(tok, "isolate_host", "ws-0042", 140.1)
    say(f"[4] PEP executes -> {ok} ({why})")
    ok, why = W.pep.execute(tok, "isolate_host", "ws-0042", 141.0)
    say(f"[5] replay of the same warrant -> {ok} ({why})")
    ok, why = W.pep.execute(tok, "isolate_host", "srv-001", 141.0)
    say(f"[6] same warrant used on another asset -> {ok} ({why})")
    forged = tok[:-8] + ("A" * 8 if not tok.endswith("A" * 8) else "B" * 8)
    ok, why = W.pep.execute(forged, "isolate_host", "ws-0042", 141.0)
    say(f"[7] tampered signature -> {ok} ({why})")

    h = W.propose("disable_account", "acct-u00007", [e.evidence_id], claimed=0.99, t=150.0)
    say(f"[8] hallucinated proposal citing evidence of ws-0042 for acct-u00007 -> {W.gw.admit(h, 150.0).verdict}")
    inj = W.propose("isolate_server", "srv-001", ["E-does-not-exist"], claimed=0.99, t=150.0)
    say(f"[9] injected proposal with non-existent evidence, claimed confidence 0.99 -> {W.gw.admit(inj, 150.0).verdict}")
    e2 = W.observe("ws-0077", t_obs=200.0, score=0.20)
    e2.score = 0.99                                   # forged off-chain analytics record
    t = W.propose("isolate_host", "ws-0077", [e2.evidence_id], claimed=0.99, t=215.0)
    say(f"[10] tampered SIEM record (score 0.20 -> 0.99) -> {W.gw.admit(t, 215.0).verdict}")

    e3 = W.observe("ws-0100", t_obs=300.0, score=0.97, lc=40.0)
    q = W.propose("isolate_host", "ws-0100", [e3.evidence_id], t=310.0)
    d = W.gw.admit(q, 310.0)
    say(f"[11] ledger confirmation delayed by 40 s: at t=310 s -> {d.verdict} (wait until <= {d.t_wait_max:.1f} s)")
    d = W.admit_until_done(q, 310.0)
    say(f"     after finality -> {d.verdict}")
    W.policies.add_change(W.policies.partition("isolate_host", "ws-0100"), 345.0, permit=True)
    r = W.gw.revalidate(d.token, 350.0)
    say(f"[12] policy partition changed (still permitted) before execution -> {r.verdict}")
    d2 = W.gw.reissue(d.token, 350.0)
    r2 = W.gw.revalidate(d2.token, 350.1)
    say(f"     re-issued -> {d2.verdict}; revalidation -> {r2.verdict}")

    e4 = W.observe("ws-0200", t_obs=400.0, score=0.97)
    s = W.propose("isolate_host", "ws-0200", [e4.evidence_id], t=410.0)
    d = W.gw.admit(s, 410.0)
    W.ledger.retract(e4.tx_id, 430.0)
    say(f"[13] evidence retracted after issuance; revalidation -> {W.gw.revalidate(d.token, 440.0).verdict}")

    e5 = W.observe("ip-10.20.1.5", t_obs=500.0, score=0.97, sensor="suricata")
    old = W.propose("block_ip", "ip-10.20.1.5", [e5.evidence_id], t=1150.0)
    say(f"[14] evidence older than Phi (600 s), deadline still reachable -> {W.gw.admit(old, 1150.0).verdict}")
    e6 = W.observe("ws-0300", t_obs=500.0, score=0.97)
    late = W.propose("isolate_host", "ws-0300", [e6.evidence_id], t=900.0)
    say(f"     isolate_host 400 s after the observation (D = 300 s) -> {W.gw.admit(late, 900.0).verdict}")
    from .ledger import Behaviour
    W.ledger.behaviour[0] = Behaviour("fabricate")
    fake = W.observe("ws-0400", t_obs=1000.0, score=0.97, anchor=False)
    fake.tx_id = "0xtx-fabricated"
    f = W.propose("isolate_host", "ws-0400", [fake.evidence_id], t=1010.0)
    say(f"[15] one Byzantine validator vouches for a non-existent record -> {W.gw.admit(f, 1010.0).verdict}")
    return log
