"""The 27 implementation checks of Section 4.6.

``recovery-evidence checks`` runs them and writes ``control_checks.txt``.  Each
check is a small function returning a one-line detail string and raising
``AssertionError`` on failure.  The same functions are executed by pytest
(``tests/test_control_checks.py``), so the text file and the test suite cannot
drift apart.
"""
from __future__ import annotations

import hashlib
import itertools
import tempfile
from fractions import Fraction as Fr
from pathlib import Path
from typing import Callable, List, Tuple

from .conditions import get_condition
from .generator import Notice, constant_trajectory, generate
from .policies import POLICIES, priorities, select, urgency
from .simulation import Operator, evaluate, reference_labels, run_policy
from .topology import operator_map_c8, less_sharing_map_c9, reference_map

# Worked example of Section 3.4 (components A..H)
EX_Z = (1, 1, 1, 0, 1, 1, 1, 1)
EX_AGES = (3, 10, 4, 8, 2, 1, 2, 9)
EX_N = (0, 0, 0, 0, 1, 0, 0, 0)
EX_W = 7

CHECKS: List[Tuple[str, Callable[[], str]]] = []


def check(title: str):
    def deco(fn):
        CHECKS.append((title, fn))
        return fn
    return deco


def _example_selection(policy: str) -> str:
    ref = reference_map()
    return ref.components[select(priorities(policy, ref, EX_Z, EX_AGES, EX_N, EX_W))]


# -- worked example (Section 3.4) ------------------------------------------
@check("Worked example: urgency u = (4, 11, 5, 9, 10, 2, 3, 10)")
def c01():
    u = urgency(EX_AGES, EX_N, EX_W)
    assert u == (4, 11, 5, 9, 10, 2, 3, 10), u
    return f"u = {u}"


@check("Worked example: current influence D(z) = (3, 1, 1, 0, 2, 2, 1, 1)")
def c02():
    d = reference_map().influence(EX_Z)
    assert d == (3, 1, 1, 0, 2, 2, 1, 1), d
    return f"D = {d}"


@check("Static importance c = (0.625, 0.1875, 0.1875, 0.125, 0.125, 0.375, 0.25, 0.25), exact fractions")
def c03():
    c = reference_map().static_importance
    want = (Fr(5, 8), Fr(3, 16), Fr(3, 16), Fr(1, 8), Fr(1, 8), Fr(3, 8), Fr(1, 4), Fr(1, 4))
    assert c == want, c
    return "c = (" + ", ".join(str(x) for x in c) + ")"


@check("Worked example: P3 priorities = (16, 22, 10, 9, 30, 6, 6, 20)")
def c04():
    p = priorities("P3", reference_map(), EX_Z, EX_AGES, EX_N, EX_W)
    assert p == (16, 22, 10, 9, 30, 6, 6, 20), p
    return f"P3 priorities = {p}"


@check("Worked example: P2 priorities B = 13.0625, E = 11.25, H = 12.5")
def c05():
    p = priorities("P2", reference_map(), EX_Z, EX_AGES, EX_N, EX_W)
    assert (p[1], p[4], p[7]) == (Fr(209, 16), Fr(45, 4), Fr(25, 2)), p
    return f"B = {float(p[1])}, E = {float(p[4])}, H = {float(p[7])}"


@check("Worked example: selections P0, P1, P2, P3 = B, B, B, E")
def c06():
    sel = tuple(_example_selection(p) for p in POLICIES)
    assert sel == ("B", "B", "B", "E"), sel
    return "selections = " + ", ".join(sel)


# -- audit cases (Appendix A) ----------------------------------------------
def _audit_case(hidden: Tuple[int, ...]):
    ref = reference_map()
    truth = ref.readiness(hidden)
    out = {}
    for pol in ("P1", "P3"):
        j = select(priorities(pol, ref, EX_Z, EX_AGES, EX_N, EX_W))
        z = list(EX_Z)
        z[j] = hidden[j]
        verdict = ref.readiness(z)
        out[pol] = (verdict, sum(1 for v, y in zip(verdict, truth) if v == 1 and y == 0))
    return truth, out


@check("Audit case I: hidden E = 0 -> truth (0,0,1); falsely assured P1 / P3 = 2 / 0; difference -66.67")
def c07():
    truth, out = _audit_case((1, 1, 1, 0, 0, 1, 1, 1))
    assert truth == (0, 0, 1) and out["P1"] == ((1, 1, 1), 2) and out["P3"] == ((0, 0, 1), 0)
    d = 100 * (out["P3"][1] - out["P1"][1]) / 3
    assert round(d, 2) == -66.67
    return f"truth {truth}; P1 record {out['P1'][0]}; P3 record {out['P3'][0]}; d = {d:.2f}"


@check("Audit case II: hidden B = 0 -> truth (0,1,1); falsely assured P1 / P3 = 0 / 1; difference +33.33")
def c08():
    truth, out = _audit_case((1, 0, 1, 0, 1, 1, 1, 1))
    assert truth == (0, 1, 1) and out["P1"] == ((0, 1, 1), 0) and out["P3"] == ((1, 1, 1), 1)
    d = 100 * (out["P3"][1] - out["P1"][1]) / 3
    assert round(d, 2) == 33.33
    return f"truth {truth}; P1 record {out['P1'][0]}; P3 record {out['P3'][0]}; d = +{d:.2f}"


# -- independent enumeration of all 256 states ------------------------------
def _closed_form_g(v):
    A, B, C, D, E, F, G, H = v
    de = max(D, E)
    return (A * B * de * F, A * C * de * F, A * G * H)


@check("All 256 states: readiness g equals the closed-form products of Section 3.2")
def c09():
    ref = reference_map()
    for v in itertools.product((0, 1), repeat=8):
        assert ref.readiness(v) == _closed_form_g(v) == ref.readiness_fast(v), v
    return "256 states compared"


@check("All 256 states: D_j equals an independent bit-flip count on the closed form")
def c10():
    ref = reference_map()
    for v in itertools.product((0, 1), repeat=8):
        base = _closed_form_g(v)
        want = tuple(
            sum(abs(a - b) for a, b in zip(base, _closed_form_g(v[:j] + (1 - v[j],) + v[j + 1:])))
            for j in range(8))
        assert ref.influence(v) == want, v
    return "256 x 8 influence values compared"


@check("Static importance equals the summed Birnbaum structural importance (exact fractions)")
def c11():
    # closed forms: a component is critical for a service when all other requirement groups are satisfied
    half, three_q = Fr(1, 2), Fr(3, 4)
    s12_single = Fr(1, 4) * three_q     # two other mandatory components, and D or E
    s12_pair = Fr(1, 8) * half          # three mandatory components, and the partner incapable
    s3_single = Fr(1, 4)
    want = (2 * s12_single + s3_single, s12_single, s12_single, 2 * s12_pair, 2 * s12_pair,
            2 * s12_single, s3_single, s3_single)
    assert reference_map().static_importance == want, want
    return "closed-form sums match for A..H"


# -- limiting behaviour ------------------------------------------------------
def _small(cond_name: str, **changes):
    return get_condition(cond_name).with_(**changes)


@check("b = m with a correct map: zero false assurances and zero false rejections")
def c12():
    cond = _small("C0", b=8)
    ref = reference_map()
    for r in range(5):
        traj = generate(cond, r, ref.components)
        for pol in POLICIES:
            s = evaluate(run_policy(traj, pol, ref, cond.b, cond.w).verdicts, reference_labels(traj, ref))
            assert s.false_assured == 0 and s.false_rejected == 0, (r, pol)
    return "5 replicates x 4 policies, 0 errors"


@check("No transitions (p_fail = 0): every verdict is correct for every policy")
def c13():
    cond = _small("C0", p_fail=0.0)
    ref = reference_map()
    traj = generate(cond, 0, ref.components)
    assert all(all(row) for row in traj.states)
    for pol in POLICIES:
        s = evaluate(run_policy(traj, pol, ref, cond.b, cond.w).verdicts, reference_labels(traj, ref))
        assert s.correct == s.service_days == 540
    return "540 of 540 service-days correct for P0-P3"


@check("b = 0: no checks, no test-module queries, records unchanged")
def c14():
    cond = get_condition("C1")
    ref = reference_map()
    traj = generate(cond, 0, ref.components)
    for pol in POLICIES:
        log = run_policy(traj, pol, ref, cond.b, cond.w)
        assert not log.checks and not log.queries and log.final_records == (1,) * 8
    return "0 checks; records stay (1,...,1)"


@check("Outcome classes (false assurance, false rejection, correct) sum to S x T")
def c15():
    cond = get_condition("C0")
    ref = reference_map()
    for r in range(3):
        traj = generate(cond, r, ref.components)
        for pol in POLICIES:
            s = evaluate(run_policy(traj, pol, ref, cond.b, cond.w).verdicts, reference_labels(traj, ref))
            assert s.false_assured + s.false_rejected + s.correct == s.service_days == 3 * 180
    return "3 replicates x 4 policies: sum = 540"


@check("Exactly min(b, m) distinct components are checked on every day")
def c16():
    ref = reference_map()
    for b in (1, 2, 4, 8, 11):
        cond = _small("C0", b=b)
        traj = generate(cond, 0, ref.components)
        for pol in POLICIES:
            log = run_policy(traj, pol, ref, cond.b, cond.w)
            per_day = {}
            for c in log.checks:
                per_day.setdefault(c.day, []).append(c.component)
            assert len(per_day) == 180
            assert all(len(v) == len(set(v)) == min(b, 8) for v in per_day.values()), (b, pol)
    return "b in {1, 2, 4, 8, 11}: min(b, 8) distinct checks per day"


@check("Test module is queried only for the selected component on the current day")
def c17():
    cond = _small("C0", b=2)
    ref = reference_map()
    traj = generate(cond, 1, ref.components)
    for pol in POLICIES:
        log = run_policy(traj, pol, ref, cond.b, cond.w)
        assert log.queries == [(c.day, c.component) for c in log.checks]
    return "query log equals check log for P0-P3"


@check("No look-ahead: inverting hidden states from day 100 on leaves decisions of days 1-99 unchanged")
def c18():
    cond = get_condition("C0")
    ref = reference_map()
    traj = generate(cond, 2, ref.components)
    flipped = [row if t < 100 else tuple(1 - v for v in row) for t, row in enumerate(traj.states)]
    alt = constant_trajectory(ref.components, cond.T, flipped, traj.notices)
    for pol in POLICIES:
        a = run_policy(traj, pol, ref, cond.b, cond.w)
        b = run_policy(alt, pol, ref, cond.b, cond.w)
        assert [c for c in a.checks if c.day < 100] == [c for c in b.checks if c.day < 100]
        assert a.verdicts[:99] == b.verdicts[:99]
    return "checks and verdicts of days 1-99 identical for P0-P3"


# -- notices -----------------------------------------------------------------
@check("Notice filter: a notice about a change on or before the last check does not set the flag")
def c19():
    op = Operator(reference_map(), "P1", 7)
    op.record(0, 5, 1)           # A checked on day 5
    op.receive([(0, 5)])         # change on day 5, delivered later
    assert op.n[0] == 0
    op.receive([(0, 4)])
    assert op.n[0] == 0
    op.receive([(0, 6)])
    assert op.n[0] == 1
    op.record(0, 7, 1)
    assert op.n[0] == 0          # a check clears the flag
    return "occurred <= tau ignored; occurred > tau sets n; check clears n"


@check("Notices: delays in {0,1,2}; late deliveries flagged; substantive notices only on changed days")
def c20():
    cond = get_condition("C0")
    ref = reference_map()
    late = 0
    for r in range(20):
        traj = generate(cond, r, ref.components)
        for n in traj.notices:
            assert n.delivered - n.occurred in (0, 1, 2)
            assert n.beyond_horizon == (n.delivered > cond.T)
            changed = traj.states[n.occurred][n.component] != traj.states[n.occurred - 1][n.component]
            assert changed == (n.kind == "substantive")
            late += n.beyond_horizon
        feed = traj.operator_feed()
        assert sum(map(len, feed)) == sum(1 for n in traj.notices if not n.beyond_horizon)
    return f"20 replicates checked; {late} notice(s) beyond the horizon kept in the log only"


@check("C6: no notice of any kind reaches the operator for A or H")
def c21():
    cond = get_condition("C6")
    ref = reference_map()
    hidden_from_operator = 0
    for r in range(20):
        traj = generate(cond, r, ref.components)
        hidden_from_operator += sum(n.suppressed for n in traj.notices)
        assert all(j not in (0, 7) for day in traj.operator_feed() for j, _ in day)
        assert all(n.suppressed == (n.component in (0, 7)) for n in traj.notices)
    assert hidden_from_operator > 0
    return f"{hidden_from_operator} generated notices for A/H withheld in 20 replicates"


@check("Deterministic C7 variant: joint failure on day 60 sets D = E = 0")
def c22():
    cond = get_condition("C7").with_(p_joint=0.0)
    ref = reference_map()
    traj = generate(cond, 0, ref.components, forced_joint_days=(60,))
    assert traj.joint_days == (60,) and traj.states[60][3] == 0 and traj.states[60][4] == 0
    return "states[60][D] = states[60][E] = 0"


@check("Deterministic C7 variant: at most one notice per component per day (start/end comparison)")
def c23():
    cond = get_condition("C7").with_(p_joint=0.0, p_report=1.0, p_nonsubstantive=0.0)
    ref = reference_map()
    for r in range(30):
        traj = generate(cond, r, ref.components, forced_joint_days=(60,))
        seen = [(n.component, n.occurred) for n in traj.notices]
        assert len(seen) == len(set(seen))
        for j in (3, 4):
            changed = traj.states[59][j] != traj.states[60][j]
            assert sum(1 for n in traj.notices if n.component == j and n.occurred == 60) == int(changed)
    return "30 replicates: one notice iff the state changed over the step"


# -- maps ----------------------------------------------------------------------
@check("C8: operator map omits F from S2 (c_F = 0.1875); evaluator map keeps it")
def c24():
    op, ev = get_condition("C8").maps()
    assert op == operator_map_c8() and ev == reference_map()
    assert op.static_importance[5] == Fr(3, 16) and ev.static_importance[5] == Fr(3, 8)
    x = (1, 1, 1, 1, 1, 0, 1, 1)  # only F incapable
    assert op.readiness(x) == (0, 1, 1) and ev.readiness(x) == (0, 0, 1)
    return "F down: operator verdict (0,1,1), reference (0,0,1)"


@check("C9: ten components in alphabetical order; A2 and F2 serve S2 only")
def c25():
    op, ev = get_condition("C9").maps()
    assert op == ev == less_sharing_map_c9() and op.m == 10
    assert op.components == ("A", "A2", "B", "C", "D", "E", "F", "F2", "G", "H")
    assert op.users("A2") == ("S2",) and op.users("F2") == ("S2",) and op.users("A") == ("S1", "S3")
    return "m = 10; users(A) = S1, S3; users(A2) = users(F2) = S2"


# -- reproducibility -----------------------------------------------------------
@check("Stream separation: changing p_report or p_nonsubstantive leaves hidden states unchanged")
def c26():
    ref = reference_map()
    base = generate(get_condition("C0"), 3, ref.components)
    for changes in ({"p_report": 0.3}, {"p_nonsubstantive": 0.2}, {"p_report": 1.0, "w": 0}):
        other = generate(get_condition("C0").with_(**changes), 3, ref.components)
        assert other.states == base.states
    sub = lambda t: [(n.component, n.occurred, n.delivered) for n in t.notices if n.kind == "substantive"]
    other = generate(get_condition("C0").with_(p_nonsubstantive=0.2), 3, ref.components)
    assert sub(other) == sub(base)
    return "states identical; substantive notices unaffected by the non-substantive rate"


@check("Repeated runs write byte-identical logs and summary tables")
def c27():
    from .experiment import LOG_FILES, run_condition

    cond = get_condition("C0")
    digests = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            run_condition(cond, Path(tmp), replicates=5)
            digests.append([hashlib.sha256((Path(tmp) / "logs" / "C0" / f).read_bytes()).hexdigest()
                            for f in LOG_FILES])
    assert digests[0] == digests[1]
    return f"{len(LOG_FILES)} files x 2 runs: SHA-256 identical"


def run_checks() -> Tuple[List[Tuple[str, bool, str]], str]:
    """Run every check; returns the results and the text of ``control_checks.txt``."""
    results: List[Tuple[str, bool, str]] = []
    for title, fn in CHECKS:
        try:
            results.append((title, True, fn()))
        except AssertionError as exc:
            results.append((title, False, f"FAILED: {exc}"))
    passed = sum(ok for _, ok, _ in results)
    lines = ["Implementation checks (Section 4.6)", "=" * 36, ""]
    for i, (title, ok, detail) in enumerate(results, start=1):
        lines.append(f"[{i:02d}] {'PASS' if ok else 'FAIL'}  {title}")
        lines.append(f"            {detail}")
    lines += ["", f"{passed} of {len(results)} checks passed."]
    return results, "\n".join(lines) + "\n"
