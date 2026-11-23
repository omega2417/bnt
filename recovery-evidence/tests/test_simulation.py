"""Sections 3.1, 3.5 and 4.4: operator, test module, evaluator."""
import pytest

from recovery_evidence.conditions import get_condition
from recovery_evidence.generator import Notice, constant_trajectory, generate
from recovery_evidence.policies import POLICIES
from recovery_evidence.simulation import TestModule, evaluate, reference_labels, run_policy
from recovery_evidence.topology import reference_map

REF = reference_map()


def test_p0_is_round_robin():
    traj = constant_trajectory(REF.components, 16)
    log = run_policy(traj, "P0", REF, 1, 7)
    assert [REF.components[c.component] for c in log.checks] == list("ABCDEFGH") * 2


def test_notice_pulls_the_event_driven_check_forward():
    notice = Notice(REF.index("G"), 1, 1, "non_substantive", None, False, False)
    traj = constant_trajectory(REF.components, 3, notices=[notice])
    assert run_policy(traj, "P1", REF, 1, 7).checks[0].component == REF.index("G")
    assert run_policy(traj, "P0", REF, 1, 7).checks[0].component == REF.index("A")


def test_sequential_selection_recomputes_influence_within_a_day():
    """b = 2: after A is found incapable every other record loses influence, so P3 falls back on urgency."""
    states = [[1] * 8, [0] + [1] * 7]
    traj = constant_trajectory(REF.components, 1, states)
    log = run_policy(traj, "P3", REF, 2, 7)
    assert [c.component for c in log.checks] == [0, 1]
    assert [c.influence for c in log.checks] == [3, 0]


def test_test_module_enforces_day_order_and_logs_queries():
    tm = TestModule([[1, 1], [0, 1], [1, 1]])
    with pytest.raises(RuntimeError):
        tm.open_day(2)
    tm.open_day(1)
    assert tm.check(0) == 0 and tm.queries == [(1, 0)]
    assert not hasattr(tm, "states") and not hasattr(tm, "_states")


def test_operator_map_must_match_trajectory_components():
    traj = constant_trajectory(("A", "B"), 2)
    with pytest.raises(ValueError):
        run_policy(traj, "P0", REF, 1, 7)


def test_evaluator_counts_and_spells():
    verdicts = [(1,), (1,), (0,), (1,), (1,), (1,)]
    labels = [(0,), (0,), (1,), (1,), (0,), (0,)]
    s = evaluate(verdicts, labels)
    assert (s.false_assured, s.false_rejected, s.correct) == (4, 1, 1)
    assert (s.spells, s.censored_spells, s.max_spell) == (2, 1, 2)
    assert s.fasd == pytest.approx(100 * 4 / 6) and s.fusd == pytest.approx(100 / 6)
    assert s.assured_days == 5 and s.unready_days == 4


def test_evaluator_rejects_unequal_horizons():
    with pytest.raises(ValueError):
        evaluate([(1,)], [(1,), (0,)])


def test_restoration_is_exogenous():
    """The hidden trajectory is the same object for every policy and is never modified by a run."""
    cond = get_condition("C0")
    traj = generate(cond, 0, REF.components)
    before = traj.states
    for pol in POLICIES:
        run_policy(traj, pol, REF, cond.b, cond.w)
    assert traj.states is before and traj == generate(cond, 0, REF.components)


def test_all_policies_identical_without_budget():
    cond = get_condition("C1")
    traj = generate(cond, 0, REF.components)
    labels = reference_labels(traj, REF)
    outs = {evaluate(run_policy(traj, p, REF, cond.b, cond.w).verdicts, labels) for p in POLICIES}
    assert len(outs) == 1 and next(iter(outs)).false_rejected == 0


def test_c8_operator_misattributes_f():
    cond = get_condition("C8")
    op, ev = cond.maps()
    states = [[1] * 8] + [[1, 1, 1, 1, 1, 0, 1, 1]] * 8  # F down for eight days
    traj = constant_trajectory(op.components, 8, states)
    log = run_policy(traj, "P0", op, 8, 7)  # every record is correct
    s = evaluate(log.verdicts, reference_labels(traj, ev))
    assert s.false_assured == 8 and s.max_spell == 8  # S2 is assured although F is down
