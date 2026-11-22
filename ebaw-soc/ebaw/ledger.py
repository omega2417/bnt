"""Permissioned evidence ledger with a masking Byzantine quorum read (Section 3.3, Eq. 6).

The ledger is simulated at the level the gateway sees it: each of n >= 4f + 1 validators
reports, at time t, the state of an evidence record (``absent``, ``pending``, ``final`` or
``retracted``) together with the digest and asset it holds.  A read quorum Q of size
ceil((n + 2f + 1) / 2) is queried and the ledger state is the most advanced state that at
least f + 1 members of Q report *identically* (same state, digest and asset).  A faulty
validator may withhold, fabricate or equivocate; with at most f faulty validators it can
neither forge nor suppress a committed state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

STATE_ORDER = {"absent": 0, "pending": 1, "final": 2, "retracted": 3}


def read_quorum_size(n: int, f: int) -> int:
    return math.ceil((n + 2 * f + 1) / 2)


@dataclass
class Anchor:
    tx_id: str
    digest: str
    asset: str
    t_submit: float
    accept: list                 # per-validator acceptance (finality) times
    t_retract: float = math.inf  # retraction transaction (exonerating evidence)

    def t_final(self, quorum: int) -> float:
        """Time at which the record is final at ``quorum`` honest validators."""
        return sorted(self.accept)[quorum - 1]


@dataclass
class Behaviour:
    """Fault model of one validator."""
    kind: str = "honest"         # honest | crash | withhold | fabricate | equivocate
    fake_digest: str = "f" * 64


@dataclass
class QuorumLedger:
    n: int = 5
    f: int = 1
    anchors: dict = field(default_factory=dict)
    behaviour: dict = field(default_factory=dict)  # validator index -> Behaviour

    def __post_init__(self):
        if self.n < 4 * self.f + 1:
            raise ValueError("a masking quorum system needs n >= 4f + 1")
        self.q = read_quorum_size(self.n, self.f)

    # ---- write path
    def anchor(self, tx_id: str, digest: str, asset: str, t_submit: float, accept: list) -> Anchor:
        if len(accept) != self.n:
            raise ValueError("one acceptance time per validator")
        a = Anchor(tx_id, digest, asset, t_submit, list(accept))
        self.anchors[tx_id] = a
        return a

    def retract(self, tx_id: str, t: float):
        self.anchors[tx_id].t_retract = t

    # ---- validator view
    def _honest_report(self, i: int, a: Anchor | None, t: float):
        if a is None or t < a.t_submit:
            return ("absent", None, None)
        if t < a.accept[i]:
            return ("pending", a.digest, a.asset)
        if t >= a.t_retract:
            return ("retracted", a.digest, a.asset)
        return ("final", a.digest, a.asset)

    def report(self, i: int, tx_id: str, t: float, asset_hint: str | None = None):
        a = self.anchors.get(tx_id)
        b = self.behaviour.get(i, Behaviour())
        if b.kind == "crash":
            return None                                   # no response (timeout)
        if b.kind == "withhold":
            return ("absent", None, None)
        if b.kind == "fabricate":
            return ("final", b.fake_digest, asset_hint)   # vouches for a record that does not exist
        if b.kind == "equivocate":
            return ("final", b.fake_digest, asset_hint) if i % 2 else ("absent", None, None)
        return self._honest_report(i, a, t)

    def quorum_read(self, tx_id: str, t: float, members: list | None = None, asset_hint: str | None = None):
        """Return (state, digest, asset, n_votes).  Fail-closed: if no state reaches f + 1
        identical reports (e.g. too many crashes), the result is ``("absent", None, None, 0)``."""
        members = list(range(self.q)) if members is None else list(members)
        if len(members) < self.q:
            return ("absent", None, None, 0)
        votes: dict = {}
        for i in members:
            r = self.report(i, tx_id, t, asset_hint)
            if r is not None:
                votes[r] = votes.get(r, 0) + 1
        ok = [(STATE_ORDER[k[0]], k, v) for k, v in votes.items() if v >= self.f + 1]
        if not ok:
            return ("absent", None, None, 0)
        _, k, v = max(ok, key=lambda o: (o[0], o[2]))
        return (k[0], k[1], k[2], v)
