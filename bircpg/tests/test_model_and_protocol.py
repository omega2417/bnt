"""Model boundaries (Section 4), Algorithm 1 bookkeeping and the statistical plan."""

import random
from fractions import Fraction

import pytest

from bircpg.baselines import default_methods
from bircpg.environments import EnvironmentConfig, make_environment, task_count_for
from bircpg.game import (
    Action,
    CostModel,
    OUTSIDE,
    ResourceCaps,
    ResourceVector,
    Task,
    TaskAllocationGame,
    linear_congestion,
)
from bircpg.metrics import endpoints, holm_adjust, paired_bootstrap, time_to_threshold
from bircpg.protocol import run_trial
from bircpg.study import CONDITIONS, StudyDesign, paired_comparison, run_study


# ------------------------------------------------------------------ Section 4
def test_assumption_A1_requires_a_nonempty_feasible_set_containing_the_fallback():
    tasks = [Task(Fraction(1))]
    with pytest.raises(ValueError):
        TaskAllocationGame(tasks, [[]])
    with pytest.raises(ValueError):
        TaskAllocationGame(tasks, [[Action(0, 0)]])  # no outside action


def test_the_outside_action_has_zero_payoff_and_zero_cost():
    game = TaskAllocationGame([Task(Fraction(5))], [[Action(0, 0), OUTSIDE]] * 2)
    assert game.payoff(0, (OUTSIDE, OUTSIDE)) == 0
    assert game.d(0, OUTSIDE) == 0
    with pytest.raises(ValueError):
        TaskAllocationGame(
            [Task(Fraction(5))], [[Action(0, 0), OUTSIDE]] * 2, {(0, OUTSIDE): Fraction(1)}
        )


def test_welfare_equals_the_sum_of_payoffs():
    game = TaskAllocationGame(
        [Task(Fraction(6), linear_congestion(Fraction(1, 10))), Task(Fraction(4))],
        [[Action(0, 0), Action(1, 0), OUTSIDE]] * 3,
        {(i, Action(j, 0)): Fraction(1, 4) for i in range(3) for j in range(2)},
    )
    for profile in game.profiles():
        assert game.welfare(profile) == sum(game.payoffs(profile))


def test_congestion_is_shared_by_every_participant_assumption_A3():
    game = TaskAllocationGame(
        [Task(Fraction(8), linear_congestion(Fraction(1, 2)))],
        [[Action(0, 0), OUTSIDE]] * 2,
    )
    profile = (Action(0, 0), Action(0, 0))
    assert game.payoff(0, profile) == game.payoff(1, profile)


def test_nash_gap_is_nonnegative_and_zero_exactly_at_equilibrium():
    from bircpg.level1 import random_instance

    game = random_instance(3, 2, seed=9)
    for profile in game.profiles():
        gap = game.nash_gap(profile)
        assert gap >= 0
        assert (gap == 0) == game.is_nash_equilibrium(profile)


def test_cost_model_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        CostModel(w_E=0.5, w_C=0.5, w_K=0.5, w_L=0.0, w_R=0.0)
    with pytest.raises(ValueError):
        CostModel(E_ref=0.0)


def test_equation2_is_a_weighted_normalised_sum():
    model = CostModel(w_E=0.5, w_C=0.5, w_K=0.0, w_L=0.0, w_R=0.0, E_ref=2.0, C_ref=4.0)
    assert model.cost(ResourceVector(energy=2.0, compute=4.0)) == pytest.approx(1.0)


def test_resource_caps_filter_the_action_set_equation_1():
    caps = ResourceCaps(energy=1.0)
    assert caps.admits(ResourceVector(energy=0.9))
    assert not caps.admits(ResourceVector(energy=1.1))


# ------------------------------------------------------------- Section 7.2
def test_task_density_levels_of_table3():
    assert task_count_for(50, "nominal") == 10
    assert task_count_for(50, "scarce") == 5
    assert task_count_for(50, "abundant") == 25
    with pytest.raises(ValueError):
        task_count_for(10, "unknown")


def test_the_environment_stream_is_independent_of_the_method():
    """Differing control flow must not change the environment a method faces."""
    config = EnvironmentConfig(n_agents=8, epochs=5, value_change_period=2)
    methods = default_methods()
    traces = []
    for method in methods[:3]:
        env = make_environment(config, seed=4)
        run = run_trial(env, method, seed=4)
        traces.append([tuple(env.values) for _ in [0]] + [r.context_events for r in run.records])
    assert traces[0][1:] == traces[1][1:] == traces[2][1:]


def test_scheduled_value_changes_and_dropout_are_recorded():
    config = EnvironmentConfig(
        n_agents=10, epochs=12, value_change_period=4, dropout_epoch=8, dropout_fraction=0.2
    )
    env = make_environment(config, seed=1)
    run = run_trial(env, default_methods()[0], seed=1)
    events = [e for r in run.records for e in r.context_events]
    assert any(e.startswith("value_change") for e in events)
    assert any(e.startswith("dropout") for e in events)
    assert run.records[-1].active_agents < 10


def test_a_dropped_agent_keeps_only_the_fallback():
    config = EnvironmentConfig(n_agents=4, epochs=1, dropout_epoch=1, dropout_fraction=0.5)
    env = make_environment(config, seed=2)
    env.advance()
    game = env.stage_game()
    for i, active in enumerate(env.active):
        if not active:
            assert game.action_sets[i] == [OUTSIDE]


# ------------------------------------------------------------- Algorithm 1
def test_every_epoch_records_its_termination_reason():
    env = make_environment(EnvironmentConfig(n_agents=6, epochs=8), seed=3)
    run = run_trial(env, default_methods()[0], seed=3)
    assert all(r.terminated in ("certified", "budget", "single-pass") for r in run.records)
    assert len(run.records) == 8


def test_the_logit_branch_never_reports_a_certificate():
    from bircpg.baselines import ReferenceBiasedLogit

    env = make_environment(EnvironmentConfig(n_agents=6, epochs=5), seed=3)
    run = run_trial(env, ReferenceBiasedLogit(tau=0.2), seed=3)
    assert all(r.terminated == "budget" for r in run.records)
    assert all(r.true_gap_bound is None for r in run.records)


def test_the_robust_branch_with_exact_payoffs_reaches_a_zero_true_gap():
    from bircpg.baselines import RobustImprovement

    env = make_environment(EnvironmentConfig(n_agents=6, epochs=4), seed=5)
    run = run_trial(env, RobustImprovement(), seed=5)
    assert run.records[-1].terminated == "certified"
    assert run.records[-1].true_nash_gap == pytest.approx(0.0)


def test_the_incumbent_is_preserved_where_it_stays_feasible():
    env = make_environment(EnvironmentConfig(n_agents=6, epochs=3), seed=6)
    run = run_trial(env, default_methods()[0], seed=6)
    assert run.records[1].profile == run.records[2].profile


def test_oracle_advantage_is_labelled():
    methods = {m.name: m for m in default_methods()}
    assert methods["B4-exact-best-response"].uses_true_payoffs
    assert methods["B5-centralised-welfare"].uses_true_payoffs
    assert not methods["proposed-logit"].uses_true_payoffs
    assert not methods["B2-uniform-logit"].uses_true_payoffs


def test_B2_is_the_proposed_logit_with_a_uniform_reference():
    methods = {m.name: m for m in default_methods()}
    assert methods["B2-uniform-logit"].uses_trace is False
    assert methods["proposed-logit"].uses_trace is True


def test_B1_and_B3_are_not_occupancy_sensitive():
    methods = {m.name: m for m in default_methods()}
    assert not methods["B1-independent-greedy"].occupancy_sensitive
    assert not methods["B3-trace-heuristic"].occupancy_sensitive


def test_B5_reports_whether_its_answer_is_exact_or_heuristic():
    from bircpg.baselines import CentralisedWelfare, EpisodeContext
    from bircpg.estimation import ExactEstimator

    env = make_environment(EnvironmentConfig(n_agents=4), seed=1)
    game = env.stage_game()
    ctx = EpisodeContext(
        trace=[0.0] * env.n_tasks,
        rng=random.Random(0),
        estimator=ExactEstimator(game.n_agents),
        update_budget=10,
    )
    exact = CentralisedWelfare().coordinate(game, [OUTSIDE] * game.n_agents, ctx)
    assert exact.notes["optimality"] == "exact"
    heuristic = CentralisedWelfare(max_profiles=1).coordinate(game, [OUTSIDE] * game.n_agents, ctx)
    assert heuristic.notes["optimality"] == "heuristic"


# ------------------------------------------------------------- Sections 7.4-7.5
def test_a_run_that_never_reaches_the_tolerance_is_censored_not_zero():
    env = make_environment(EnvironmentConfig(n_agents=6, epochs=4), seed=7)
    run = run_trial(env, default_methods()[2], seed=7)   # B1, which does not converge
    evaluations, reached = time_to_threshold(run, tolerance=-1.0)
    assert evaluations is None and reached is False
    ep = endpoints(run, gap_tolerance=-1.0)
    assert ep.evaluations_to_threshold is None
    assert ep.reached_threshold is False


def test_paired_bootstrap_drops_censored_pairs_instead_of_imputing_them():
    result = paired_bootstrap(
        [1.0, 2.0, 3.0, 99.0],
        [0.0, 1.0, 2.0, 0.0],
        resamples=500,
        rng=random.Random(0),
        censored=[False, False, False, True],
    )
    assert result.n_pairs == 3
    assert result.censored_pairs == 1
    assert result.mean_difference == pytest.approx(1.0)


def test_paired_bootstrap_rejects_misaligned_samples():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0], [1.0, 2.0])


def test_holm_is_monotone_and_never_below_the_raw_p_value():
    adjusted = holm_adjust([0.001, 0.02, 0.03, 0.9])
    values = [row["p_holm"] for row in adjusted]
    assert all(row["p_holm"] >= row["p_raw"] for row in adjusted)
    assert values == sorted(values)
    assert all(v <= 1.0 for v in values)


def test_all_six_prespecified_conditions_run():
    design = StudyDesign(
        population_sizes=(6,), conditions=tuple(CONDITIONS), seeds=1, epochs=4
    )
    results = run_study(design, methods=default_methods()[:2])
    assert len({r.condition for r in results}) == len(CONDITIONS)


def test_methods_are_paired_on_identical_environmental_seeds():
    design = StudyDesign(population_sizes=(8,), conditions=("stationary_nominal",),
                         seeds=4, epochs=6)
    results = run_study(design, methods=default_methods()[:2])
    comparison = paired_comparison(
        results, "proposed-robust", "proposed-logit", "cumulative_welfare",
        resamples=200, rng=random.Random(0),
    )
    assert comparison.n_pairs == 4


# ------------------------------------------------------- Section 7.6 seeds
def test_seed_derivation_is_stable_across_processes():
    """"Seed 7" must denote the same instance in every process, or no table is
    reproducible.  Python's built-in hash of a string is randomised per process,
    so a stable hash is used instead -- this test runs a fresh interpreter with
    a different PYTHONHASHSEED and compares."""
    import os
    import subprocess
    import sys

    script = (
        "import sys; sys.path.insert(0, 'src');"
        "from bircpg.seeds import derive_seed;"
        "from bircpg.level1 import random_instance;"
        "g = random_instance(3, 2, seed=7);"
        "print(derive_seed('environment', 3, 10));"
        "print([str(t.value) for t in g.tasks])"
    )
    outputs = []
    for hashseed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        out = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, env=env, check=True
        )
        outputs.append(out.stdout)
    assert outputs[0] == outputs[1], "seeded generation depends on PYTHONHASHSEED"


def test_the_same_seed_reproduces_the_same_run():
    config = EnvironmentConfig(n_agents=8, epochs=10, observation_noise=0.1)
    method = default_methods()[1]
    first = run_trial(make_environment(config, seed=42), method, seed=42)
    second = run_trial(make_environment(config, seed=42), method, seed=42)
    assert first.series("welfare") == second.series("welfare")
    assert [r.profile for r in first.records] == [r.profile for r in second.records]
