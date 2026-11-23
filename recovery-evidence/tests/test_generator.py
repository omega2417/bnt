"""Section 4.1: generator, random streams and notices."""
import numpy as np

from recovery_evidence.conditions import get_condition, load_conditions
from recovery_evidence.generator import generate, stream
from recovery_evidence.topology import reference_map

REF = reference_map()


def test_thirteen_conditions_with_unique_ids():
    conds = load_conditions()
    assert [c.name for c in conds] == [f"C{i}" for i in range(13)]
    assert [c.id for c in conds] == list(range(13))


def test_table4_parameters():
    c0 = get_condition("C0")
    assert (c0.T, c0.R, c0.b, c0.p_fail, c0.p_rec, c0.p_report, c0.p_nonsubstantive, c0.w) == \
        (180, 300, 1, 0.02, 0.20, 0.8, 0.01, 7)
    assert c0.delay_values == (0, 1, 2) and c0.root_entropy == 20261123
    assert [get_condition(n).b for n in ("C1", "C2", "C3")] == [0, 2, 4]
    assert [get_condition(n).p_report for n in ("C4", "C5")] == [0.3, 1.0]
    assert get_condition("C6").suppressed_components == ("A", "H")
    assert get_condition("C7").p_joint == 0.005
    assert [get_condition(n).w for n in ("C10", "C11", "C12")] == [0, 3, 14]


def test_each_condition_changes_one_factor():
    base = get_condition("C0").to_dict()
    for cond in load_conditions()[1:]:
        d = cond.to_dict()
        changed = {k for k in d if d[k] != base[k]} - {"id", "name", "label", "question"}
        if cond.name == "C9":
            assert changed == {"operator_map", "evaluator_map"}
        else:
            assert len(changed) == 1, (cond.name, changed)


def test_stream_definition_matches_documentation():
    """SeedSequence(root, spawn_key=(configuration, replicate, stream)) with PCG64."""
    a = stream(20261123, 0, 0, 0).random(3)
    seq = np.random.SeedSequence(20261123, spawn_key=(0, 0, 0))
    b = np.random.Generator(np.random.PCG64(seq)).random(3)
    assert (a == b).all()


def test_transitions_follow_the_documented_block():
    cond = get_condition("C0")
    traj = generate(cond, 7, REF.components)
    u = stream(cond.root_entropy, cond.id, 7, 0).random((cond.T + 1, 8))
    x = [1] * 8
    for t in range(1, cond.T + 1):
        x = [(0 if u[t, j] < 0.02 else 1) if x[j] else (1 if u[t, j] < 0.20 else 0) for j in range(8)]
        assert tuple(x) == traj.states[t]


def test_generation_is_deterministic_and_replicates_differ():
    cond = get_condition("C0")
    assert generate(cond, 4, REF.components) == generate(cond, 4, REF.components)
    assert generate(cond, 4, REF.components).states != generate(cond, 5, REF.components).states


def test_conditions_use_independent_trajectories():
    a = generate(get_condition("C0"), 0, REF.components)
    b = generate(get_condition("C4"), 0, REF.components)
    assert a.states != b.states


def test_stationary_incapability_is_about_nine_percent():
    cond = get_condition("C0")
    down = total = 0
    for r in range(60):
        traj = generate(cond, r, REF.components)
        down += sum(row.count(0) for row in traj.states[1:])
        total += 8 * cond.T
    assert 0.075 < down / total < 0.10


def test_reporting_probability_and_non_substantive_rate():
    cond = get_condition("C0")
    changes = sub = nonsub = quiet = 0
    for r in range(60):
        traj = generate(cond, r, REF.components)
        for t in range(1, cond.T + 1):
            for j in range(8):
                if traj.states[t][j] != traj.states[t - 1][j]:
                    changes += 1
                else:
                    quiet += 1
        sub += sum(n.kind == "substantive" for n in traj.notices)
        nonsub += sum(n.kind == "non_substantive" for n in traj.notices)
    assert 0.76 < sub / changes < 0.84
    assert 0.008 < nonsub / quiet < 0.012


def test_complete_reporting_in_c5():
    cond = get_condition("C5")
    traj = generate(cond, 0, REF.components)
    changes = sum(traj.states[t][j] != traj.states[t - 1][j] for t in range(1, 181) for j in range(8))
    assert sum(n.kind == "substantive" for n in traj.notices) == changes


def test_joint_degradation_only_in_c7():
    assert generate(get_condition("C0"), 0, REF.components).joint_days == ()
    days = [d for r in range(40) for d in generate(get_condition("C7"), r, REF.components).joint_days]
    assert 15 < len(days) < 60  # expectation 40 x 180 x 0.005 = 36
