"""Phylogenetic signal, convergence and the analytic results of Appendix A."""

import numpy as np
import pytest

from evoproto import phylo


def test_vcv_is_symmetric_positive_definite_and_ultrametric():
    tree = phylo.random_ultrametric_tree(12, seed=1)
    C = phylo.vcv_matrix(tree)
    assert np.allclose(C, C.T)
    assert np.all(np.linalg.eigvalsh(C) > 0)
    # ultrametric: every tip sits at the same depth, so the diagonal is constant
    assert np.allclose(np.diag(C), np.diag(C)[0])


def test_blombergs_k_has_expectation_one_under_brownian_motion():
    """Appendix A.1: E[K] = 1 under BM on the given tree."""
    tree = phylo.random_ultrametric_tree(20, seed=2)
    C = phylo.vcv_matrix(tree)
    values = [
        phylo.blombergs_k(phylo.simulate_brownian(tree, 1.0, seed=s)[0], C)
        for s in range(300)
    ]
    assert np.mean(values) == pytest.approx(1.0, abs=0.12)


def test_blombergs_k_is_scale_invariant():
    tree = phylo.random_ultrametric_tree(15, seed=4)
    C = phylo.vcv_matrix(tree)
    x, _ = phylo.simulate_brownian(tree, 1.0, seed=5)
    assert phylo.blombergs_k(10.0 * x + 3.0, C) == pytest.approx(phylo.blombergs_k(x, C))


def test_expected_k_denominator_matches_equation_a1():
    tree = phylo.random_ultrametric_tree(9, seed=6)
    C = phylo.vcv_matrix(tree)
    n = C.shape[0]
    ones = np.ones(n)
    expected = (np.trace(C) - n / (ones @ np.linalg.solve(C, ones))) / (n - 1)
    assert phylo.expected_k_denominator(C) == pytest.approx(expected)


def test_pagels_lambda_is_high_for_brownian_and_low_for_white_noise():
    tree = phylo.random_ultrametric_tree(30, seed=7)
    C = phylo.vcv_matrix(tree)
    brownian, _ = phylo.simulate_brownian(tree, 1.0, seed=8)
    rng = np.random.default_rng(9)
    noise = rng.normal(size=len(tree.tips))
    assert phylo.pagels_lambda(brownian, C) > 0.7
    assert phylo.pagels_lambda(noise, C) < 0.4


def test_lambda_profile_peaks_at_the_maximum_likelihood_estimate():
    tree = phylo.random_ultrametric_tree(16, seed=10)
    C = phylo.vcv_matrix(tree)
    x, _ = phylo.simulate_brownian(tree, 1.0, seed=11)
    grid, loglik = phylo.lambda_profile(x, C)
    lam = phylo.pagels_lambda(x, C)
    assert abs(grid[int(np.argmax(loglik))] - lam) < 0.05


def test_ancestral_states_match_the_joint_maximum_likelihood_solution():
    """The two-pass pruning result must solve min sum_edges (x_c - x_p)^2 / bl."""
    tree = phylo.random_ultrametric_tree(14, seed=12)
    tips, _ = phylo.simulate_brownian(tree, 1.0, seed=13)
    estimated = phylo.ancestral_states(tree, tips)

    internal = [n for n in range(tree.n_nodes) if n not in tree.tips]
    index = {node: i for i, node in enumerate(internal)}
    A = np.zeros((len(internal), len(internal)))
    b = np.zeros(len(internal))
    fixed = dict(zip(tree.tips, tips))
    for node in range(tree.n_nodes):
        parent = int(tree.parent[node])
        if parent < 0:
            continue
        w = 1.0 / float(tree.branch_length[node])
        for v, sign in ((node, 1.0), (parent, -1.0)):
            if v not in index:
                continue
            for v2, sign2 in ((node, 1.0), (parent, -1.0)):
                if v2 in index:
                    A[index[v], index[v2]] += w * sign * sign2
                else:
                    b[index[v]] -= w * sign * sign2 * fixed[v2]
    joint = np.linalg.solve(A, b)
    assert np.allclose([estimated[n] for n in internal], joint, atol=1e-9)


def test_ancestral_state_of_a_two_tip_tree_is_the_branch_weighted_mean():
    tree = phylo.Tree(parent=[2, 2, -1], branch_length=[1.0, 3.0, 0.0], labels={0: "a", 1: "b"})
    states = phylo.ancestral_states(tree, [0.0, 4.0])
    assert states[2] == pytest.approx(1.0)  # weights 1/1 and 1/3


def test_stayton_c1_is_one_for_identical_tips_and_zero_without_convergence():
    """C1 = 1 - D_tip/D_max lies in [0, 1] because D_max ranges over the tips too."""
    tree = phylo.random_ultrametric_tree(12, seed=14)
    tips, _ = phylo.simulate_brownian(tree, 1.0, seed=15)
    i, j = tree.tips[0], tree.tips[-1]

    converged = np.asarray(tips, dtype=float).copy()
    converged[0] = converged[-1] = 5.0  # the two tips meet exactly
    assert phylo.stayton_c1(tree, converged, i, j) == pytest.approx(1.0)

    diverged = np.asarray(tips, dtype=float).copy()
    diverged[0], diverged[-1] = -20.0, 20.0  # the tips are further apart than any ancestors
    assert phylo.stayton_c1(tree, diverged, i, j) == pytest.approx(0.0)


def test_c1_pvalue_is_uniformish_under_the_brownian_null():
    tree = phylo.random_ultrametric_tree(12, seed=16)
    tips, _ = phylo.simulate_brownian(tree, 1.0, seed=17)
    observed, p, null = phylo.c1_pvalue(tree, tips, tree.tips[0], tree.tips[-1], n_sim=199, seed=1)
    assert 0.0 < p <= 1.0
    assert null.size == 199
    assert observed == pytest.approx(phylo.stayton_c1(tree, tips, tree.tips[0], tree.tips[-1]))


def test_c1_pvalue_is_small_for_strongly_convergent_tips():
    tree = phylo.random_ultrametric_tree(14, seed=18)
    tips, _ = phylo.simulate_brownian(tree, 1.0, seed=19)
    converged = np.asarray(tips, dtype=float).copy()
    converged[0] = converged[-1] = float(np.mean(tips))
    _, p, _ = phylo.c1_pvalue(tree, converged, tree.tips[0], tree.tips[-1], n_sim=199, seed=2)
    assert p <= 0.05
