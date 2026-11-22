"""Properties of the reference gateway core (Proposition 3 and Algorithm 1)."""
import itertools
import random

import pytest

from ebaw.demo import World
from ebaw.ledger import Behaviour, QuorumLedger, read_quorum_size
from ebaw.warrant import NonceStore, Signer, decode


@pytest.fixture(params=[False, True], ids=["ed25519", "hmac"])
def world(request):
    return World(force_hmac=request.param)


def issue(W, asset="ws-1", score=0.97, t_obs=100.0, t=112.0, action="isolate_host"):
    e = W.observe(asset, t_obs=t_obs, score=score)
    p = W.propose(action, asset, [e.evidence_id], claimed=0.99, t=t)
    return e, p, W.gw.admit(p, t)


def test_issue_revalidate_execute_once(world):
    _, _, d = issue(world)
    assert d.verdict == "ISSUE"
    assert world.pep.execute(d.token, "isolate_host", "ws-1", 120.0)[0] is False   # not committed yet
    assert world.gw.revalidate(d.token, 120.0).verdict == "EXECUTE"
    assert world.pep.execute(d.token, "isolate_host", "ws-1", 120.1)[0] is True
    assert world.pep.execute(d.token, "isolate_host", "ws-1", 120.2) == (False, "nonce already consumed (replay)")
    assert world.gw.revalidate(d.token, 121.0).verdict == "REFUSE"                  # no second commit


def test_warrant_binds_action_asset_and_expiry(world):
    _, _, d = issue(world)
    world.gw.revalidate(d.token, 120.0)
    assert world.pep.execute(d.token, "isolate_host", "ws-2", 121.0)[0] is False
    assert world.pep.execute(d.token, "kill_process", "ws-1", 121.0)[0] is False
    w = decode(d.token, world.signer.verifier())
    assert world.pep.execute(d.token, "isolate_host", "ws-1", w.exp + 1.0)[1] == "warrant expired"


def test_signature_tampering_detected(world):
    _, _, d = issue(world)
    h, c, s = d.token.split(".")
    rnd = random.Random(1)
    for _ in range(20):
        i = rnd.randrange(len(c))
        c2 = c[:i] + ("A" if c[i] != "A" else "B") + c[i + 1:]
        assert decode(f"{h}.{c2}.{s}", world.signer.verifier()) is None
    other = Signer(b"attacker", kid=world.signer.kid, force_hmac=world.signer.alg == "HS256")
    assert decode(d.token, other.verifier()) is None


def test_claimed_confidence_is_ignored(world):
    e = world.observe("ws-9", t_obs=100.0, score=0.30)
    for claimed in (0.0, 0.5, 0.99, 1.0, 1e9):
        p = world.propose("isolate_host", "ws-9", [e.evidence_id], claimed=claimed, t=110.0)
        assert world.gw.admit(p, 110.0).verdict in ("MONITOR", "ESCALATE")


@pytest.mark.parametrize("attack", ["hallucinated", "injected_missing", "tampered", "unsigned", "unanchored"])
def test_adversarial_proposals_never_issue(world, attack):
    e = world.observe("ws-1", t_obs=100.0, score=0.97)
    if attack == "hallucinated":
        p = world.propose("disable_account", "acct-1", [e.evidence_id], 0.99, 110.0)
    elif attack == "injected_missing":
        p = world.propose("isolate_server", "srv-1", ["nope"], 0.99, 110.0)
    elif attack == "tampered":
        e.score = 0.999
        p = world.propose("isolate_host", "ws-1", [e.evidence_id], 0.99, 110.0)
    elif attack == "unsigned":
        e.sensor_sig = "00" * 64
        p = world.propose("isolate_host", "ws-1", [e.evidence_id], 0.99, 110.0)
    else:
        u = world.observe("ws-5", t_obs=100.0, score=0.97, anchor=False)
        p = world.propose("isolate_host", "ws-5", [u.evidence_id], 0.99, 110.0)
    d = world.gw.admit(p, 110.0)
    assert d.verdict != "ISSUE" and d.token is None


def test_fail_closed_on_garbage_tokens(world):
    for tok in ("", "a.b", "a.b.c", "x" * 200, None):
        assert world.gw.revalidate(tok or "", 1.0).verdict == "REFUSE"
        assert world.pep.execute(tok or "", "isolate_host", "ws-1", 1.0)[0] is False


def test_pending_evidence_waits_then_issues(world):
    e = world.observe("ws-3", t_obs=100.0, score=0.97, lc=30.0)
    p = world.propose("isolate_host", "ws-3", [e.evidence_id], t=110.0)
    d = world.gw.admit(p, 110.0)
    assert d.verdict == "WAIT" and d.t_wait_max > 110.0
    assert world.admit_until_done(p, 110.0).verdict == "ISSUE"


def test_policy_change_reissue_or_reject(world):
    _, _, d = issue(world, asset="ws-4")
    part = world.policies.partition("isolate_host", "ws-4")
    world.policies.add_change(part, 115.0, permit=True)
    assert world.gw.revalidate(d.token, 120.0).verdict == "REISSUE"
    _, _, d2 = issue(world, asset="ws-5")
    world.policies.add_change(world.policies.partition("isolate_host", "ws-5"), 115.0, permit=False)
    assert world.gw.revalidate(d2.token, 120.0).verdict == "REJECT"


def test_retraction_caught_at_revalidation(world):
    e, _, d = issue(world, asset="ws-6")
    world.ledger.retract(e.tx_id, 115.0)
    assert world.gw.revalidate(d.token, 120.0).verdict == "REJECT"


def test_contract_monotonicity_pointwise():
    """Proposition 4: for a fixed state, Adm_S' implies Adm_S whenever S is a subset of S'."""
    from ebaw.model import PREDICATES
    rnd = random.Random(7)
    W = World()
    props = []
    for i in range(60):
        t_obs = rnd.uniform(0, 500)
        e = W.observe(f"ws-{i}", t_obs=t_obs, score=rnd.random(), lc=rnd.choice([0.5, 1, 40, 200]),
                      anchor=rnd.random() > 0.1)
        props.append((W.propose(rnd.choice(["isolate_host", "block_ip", "kill_process"]), f"ws-{i}",
                                [e.evidence_id], t=t_obs + rnd.uniform(5, 400)), t_obs))
    subsets = [frozenset(c) for k in range(6) for c in itertools.combinations(PREDICATES, k)]
    for p, _ in props:
        adm = {S: W.gw.evaluate(p, p.t_prop, "issue", S=S)[1] == "" for S in subsets}
        for S, S2 in itertools.product(subsets, subsets):
            if S <= S2 and adm[S2]:
                assert adm[S]


@pytest.mark.parametrize("n,f", [(5, 1), (9, 2), (13, 3)])
@pytest.mark.parametrize("fault", ["crash", "withhold", "fabricate", "equivocate"])
def test_quorum_masks_f_faults(n, f, fault):
    L = QuorumLedger(n=n, f=f)
    L.anchor("tx", "d" * 64, "ws-1", 0.0, [1.0 + 0.1 * i for i in range(n)])
    for i in range(f):
        L.behaviour[i] = Behaviour(fault)
    q = read_quorum_size(n, f)
    for members in itertools.islice(itertools.combinations(range(n), q), 50):
        st, dg, asset, _ = L.quorum_read("tx", 100.0, members)
        assert (st, dg, asset) == ("final", "d" * 64, "ws-1")
        st, *_ = L.quorum_read("missing", 100.0, members, asset_hint="ws-1")
        assert st == "absent"


def test_ledger_requires_4f_plus_1():
    with pytest.raises(ValueError):
        QuorumLedger(n=4, f=1)


def test_nonce_store_single_use():
    ns = NonceStore()
    assert ns.consume("n1", 1.0) and not ns.consume("n1", 2.0) and ns.used("n1")
