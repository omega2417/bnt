"""Propositions 1-3, Corollaries 1-2 and the Section 5.2 certificates."""

import math
import random
from fractions import Fraction

import pytest

from bircpg.equilibria import (
    improvement_path,
    potential_maximiser,
    pure_nash_equilibria,
    verify_exact_potential,
)
from bircpg.estimation import (
    BoundedNoiseEstimator,
    ExactEstimator,
    approximate_equilibrium_certificate,
    coverage_report,
    estimated_nash_gap,
    uncertainty_gated_sweep,
)
from bircpg.game import Action, OUTSIDE, Task, TaskAllocationGame, harmonic, linear_congestion
from bircpg.level1 import EDGE_CASES, edge_case_instance, random_instance
from bircpg.logit import (
    detailed_balance_residual,
    expected_potential,
    logit_choice_probabilities,
    potential_loss_bound,
    stationary_distribution,
    transition_matrix,
)
from bircpg.traces import TraceField, reference_distribution


INSTANCES = [random_instance(n, m, seed, mask_probability=0.3)
             for n in (2, 3, 4) for m in (2, 3) for seed in range(4)]
EDGE_INSTANCES = [edge_case_instance(kind) for kind in EDGE_CASES]


# ---------------------------------------------------------------- Proposition 1
@pytest.mark.parametrize("game", INSTANCES + EDGE_INSTANCES, ids=lambda g: g.label)
def test_proposition1_exact_potential_residual_is_identically_zero(game):
    check = verify_exact_potential(game)
    assert check.exact, f"residual {check.max_residual} at {check.worst_case}"


def test_harmonic_numbers_are_exact():
    assert harmonic(0) == 0
    assert harmonic(1) == 1
    assert harmonic(3) == Fraction(11, 6)


def test_potential_differs_from_welfare_in_general():
    """Equation (5) accumulates harmonically; Equation (4) counts V_j once."""
    from bircpg.section6 import A1, build_game

    game = build_game()
    profile = (A1, A1)
    assert game.welfare(profile) != game.potential(profile)


# ---------------------------------------------------------------- Corollary 1
@pytest.mark.parametrize("game", INSTANCES, ids=lambda g: g.label)
def test_corollary1_potential_maximiser_is_a_pure_nash_equilibrium(game):
    profile, _ = potential_maximiser(game)
    assert game.nash_gap(profile) <= 0


@pytest.mark.parametrize("game", INSTANCES, ids=lambda g: g.label)
def test_corollary1_improvement_paths_terminate_with_strictly_increasing_potential(game):
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    path = improvement_path(game, start)
    assert path.certified
    assert game.nash_gap(path.final) <= 0
    for before, after in zip(path.potentials, path.potentials[1:]):
        assert after > before
    assert len(set(path.profiles)) == len(path.profiles), "a profile recurred"
    assert path.length <= game.profile_count - 1


def test_budget_limited_exit_is_not_a_certificate():
    game = random_instance(4, 3, seed=7)
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    path = improvement_path(game, start, max_switches=1)
    assert path.terminated == "budget"
    assert not path.certified


# ---------------------------------------------------------------- Proposition 2
def test_proposition2_arithmetic():
    assert approximate_equilibrium_certificate(0.0, 0.3) == pytest.approx(0.6)
    assert approximate_equilibrium_certificate(0.2, 0.3) == pytest.approx(0.8)


@pytest.mark.parametrize("seed", range(6))
def test_proposition2_holds_on_random_instances(seed):
    """An eta-Nash profile of the estimated game is (eta + 2 delta)-Nash of the true game."""
    game = random_instance(3, 3, seed)
    delta = 0.25
    estimator = BoundedNoiseEstimator(delta, game.n_agents, rng=random.Random(seed))
    for profile in game.profiles():
        eta = estimated_nash_gap(game, profile, estimator)
        true_gap = float(game.nash_gap(profile))
        assert true_gap <= approximate_equilibrium_certificate(eta, estimator.delta_max) + 1e-9


@pytest.mark.parametrize("seed", range(6))
def test_equation8_gate_guarantees_a_true_gain_above_theta(seed):
    """Every accepted switch really does increase the exact potential."""
    game = random_instance(4, 3, seed)
    delta, theta = 0.2, 0.05
    estimator = BoundedNoiseEstimator(delta, game.n_agents, rng=random.Random(seed))
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    # Replay the sweep step by step and check each accepted switch against truth.
    profile = start
    while True:
        accepted = False
        for i in range(game.n_agents):
            u_hat = estimator.evaluate(game, i, profile)
            chosen, best = None, 2.0 * delta + theta
            for b in game.action_sets[i]:
                if b == profile[i]:
                    continue
                gain = estimator.evaluate(game, i, game.replace(profile, i, b)) - u_hat
                if gain > best:
                    chosen, best = b, gain
            if chosen is not None:
                before = game.potential(profile)
                true_gain = float(game.unilateral_gain(i, profile, chosen))
                assert true_gain > theta - 1e-12
                profile = game.replace(profile, i, chosen)
                assert game.potential(profile) > before
                accepted = True
        if not accepted:
            break


@pytest.mark.parametrize("seed", range(6))
def test_certified_stop_bounds_the_true_gap_by_four_delta_plus_theta(seed):
    game = random_instance(4, 3, seed)
    delta, theta = 0.15, 0.02
    estimator = BoundedNoiseEstimator(delta, game.n_agents, rng=random.Random(seed))
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    sweep = uncertainty_gated_sweep(game, start, estimator, theta=theta)
    assert sweep.certified
    assert sweep.true_gap_bound == pytest.approx(4 * delta + theta)
    assert float(game.nash_gap(sweep.profile)) <= sweep.true_gap_bound + 1e-9


def test_exact_estimator_with_zero_theta_reproduces_best_response():
    game = random_instance(4, 3, seed=11)
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    sweep = uncertainty_gated_sweep(game, start, ExactEstimator(game.n_agents))
    assert sweep.certified
    assert float(game.nash_gap(sweep.profile)) == 0.0


def test_evaluation_budget_exhaustion_is_recorded_as_such():
    game = random_instance(5, 3, seed=2)
    estimator = BoundedNoiseEstimator(0.1, game.n_agents, rng=random.Random(0))
    start = tuple(OUTSIDE for _ in range(game.n_agents))
    sweep = uncertainty_gated_sweep(game, start, estimator, evaluation_budget=3)
    assert sweep.terminated == "budget"
    assert sweep.true_gap_bound is None


def test_a_systematic_bias_larger_than_the_allowance_is_rejected():
    with pytest.raises(ValueError):
        BoundedNoiseEstimator(0.1, 3, bias=0.5)


def test_coverage_report_separates_empirical_coverage_from_the_declared_bound():
    game = random_instance(3, 2, seed=5)
    estimator = BoundedNoiseEstimator(0.2, game.n_agents, rng=random.Random(1))
    report = coverage_report(game, estimator, list(game.profiles()))
    assert report["empirical_coverage"] == 1.0
    assert report["max_abs_error"] <= report["declared_delta_max"] + 1e-12
    assert "declared_delta_max" in report


# ---------------------------------------------------------------- Proposition 3
@pytest.mark.parametrize("game", INSTANCES[:6], ids=lambda g: g.label)
@pytest.mark.parametrize("tau", [0.25, 1.0])
def test_proposition3_detailed_balance_and_stationarity(game, tau):
    refs = [
        reference_distribution(game.action_sets[i], [0.3, 0.7, 0.1][: game.n_tasks], 1.0, 0.1)
        for i in range(game.n_agents)
    ]
    profiles, P = transition_matrix(game, refs, tau)
    pi = stationary_distribution(game, refs, tau)
    residuals = detailed_balance_residual(profiles, P, pi)
    assert residuals["row_sum"] < 1e-12
    assert residuals["detailed_balance"] < 1e-12
    assert residuals["stationary"] < 1e-12
    assert sum(pi.values()) == pytest.approx(1.0)


def test_stationary_mass_concentrates_on_the_potential_maximiser_as_tau_falls():
    """As tau -> 0 the mass concentrates on the maximisers of Phi.

    The set of maximisers can have more than one element -- ties are one of the
    Level I edge cases -- so the mass is summed over all of them rather than
    assumed to sit on a single profile.
    """
    game = random_instance(3, 2, seed=3)
    refs = [
        reference_distribution(game.action_sets[i], [0.0] * game.n_tasks, 0.0, 1.0)
        for i in range(game.n_agents)
    ]
    _, best = potential_maximiser(game)
    argmaxima = [a for a in game.profiles() if game.potential(a) == best]
    masses = [
        sum(stationary_distribution(game, refs, tau)[a] for a in argmaxima)
        for tau in (2.0, 0.5, 0.1, 0.02)
    ]
    assert masses == sorted(masses)
    assert masses[-1] > 0.99
    for profile in argmaxima:
        assert game.nash_gap(profile) <= 0


def test_non_equilibria_keep_positive_mass_at_positive_temperature():
    """A favourable stationary distribution is not a point equilibrium."""
    from bircpg.section6 import build_game

    game = build_game()
    refs = [
        reference_distribution(game.action_sets[i], [0.0, 0.0], 0.0, 1.0)
        for i in range(game.n_agents)
    ]
    pi = stationary_distribution(game, refs, 1.0, active_only=True)
    for profile, mass in pi.items():
        assert mass > 0.0
    assert any(game.nash_gap(a) > 0 and p > 0.001 for a, p in pi.items())


def test_logit_rule_requires_positive_temperature_and_full_support():
    game = random_instance(2, 2, seed=1)
    refs = [
        reference_distribution(game.action_sets[i], [0.0] * game.n_tasks, 0.0, 1.0)
        for i in range(game.n_agents)
    ]
    profile = next(iter(game.profiles()))
    with pytest.raises(ValueError):
        logit_choice_probabilities(game, 0, profile, refs[0], tau=0.0)
    broken = dict(refs[0])
    broken[next(iter(broken))] = 0.0
    with pytest.raises(ValueError):
        logit_choice_probabilities(game, 0, profile, broken, tau=1.0)


def test_uniform_reference_recovers_the_standard_conditional_logit_form():
    game = random_instance(3, 2, seed=4)
    actions = game.action_sets[0]
    uniform = reference_distribution(actions, [0.0] * game.n_tasks, kappa=0.0, epsilon_z=1.0)
    profile = next(iter(game.profiles()))
    probs = logit_choice_probabilities(game, 0, profile, uniform, tau=0.7)
    total = sum(
        math.exp(float(game.payoff(0, game.replace(profile, 0, b))) / 0.7) for b in actions
    )
    for b in actions:
        expected = math.exp(float(game.payoff(0, game.replace(profile, 0, b))) / 0.7) / total
        assert probs[b] == pytest.approx(expected)


# ---------------------------------------------------------------- Corollary 2
@pytest.mark.parametrize("game", INSTANCES[:6], ids=lambda g: g.label)
@pytest.mark.parametrize("tau", [0.1, 0.5, 2.0])
def test_corollary2_potential_loss_bound_holds(game, tau):
    refs = [
        reference_distribution(game.action_sets[i], [0.2, 0.9, 0.5][: game.n_tasks], 2.0, 0.1)
        for i in range(game.n_agents)
    ]
    report = potential_loss_bound(game, refs, tau)
    assert report["realised_loss"] <= report["bound"] + 1e-9
    assert report["satisfied"]


def test_concentrated_references_weaken_the_bound():
    game = random_instance(3, 3, seed=6)
    z = [0.05, 0.95, 0.5]
    mild = [reference_distribution(game.action_sets[i], z, 0.5, 0.1) for i in range(game.n_agents)]
    sharp = [reference_distribution(game.action_sets[i], z, 8.0, 0.001) for i in range(game.n_agents)]
    assert potential_loss_bound(game, sharp, 0.5)["bound"] > potential_loss_bound(game, mild, 0.5)["bound"]


# ---------------------------------------------------------------- traces
def test_equation9_decays_towards_zero_without_reports():
    trace = TraceField(2, rho=0.5)
    trace.update({0: 1.0, 1: 1.0})
    assert trace.z[0] == pytest.approx(0.5)
    trace.update({})           # no report means s_j = 0
    assert trace.z[0] == pytest.approx(0.25)


def test_trace_delay_exposes_information_age():
    """A delayed trace keeps serving stale information after the world changed."""
    trace = TraceField(1, rho=1.0, delay=2)
    for value in (1.0, 0.0, 0.0):
        trace.update({0: value})
    assert trace.z[0] == pytest.approx(0.0)      # the trace itself is up to date
    assert trace.frozen()[0] == pytest.approx(1.0)  # what the episode reads is not
    assert trace.age == 2


def test_zero_delay_reads_the_current_trace():
    trace = TraceField(1, rho=1.0, delay=0)
    trace.update({0: 1.0})
    assert trace.frozen()[0] == pytest.approx(1.0)
    assert trace.age == 0


def test_equation10_reference_has_full_support_and_sums_to_one():
    actions = [Action(0, 0), Action(1, 0), OUTSIDE]
    q = reference_distribution(actions, [0.9, 0.1], kappa=3.0, epsilon_z=0.1)
    assert sum(q.values()) == pytest.approx(1.0)
    assert all(p > 0 for p in q.values())
    assert q[Action(0, 0)] > q[Action(1, 0)]


def test_rho_outside_its_range_is_rejected():
    with pytest.raises(ValueError):
        TraceField(2, rho=0.0)
    with pytest.raises(ValueError):
        TraceField(2, rho=1.5)
