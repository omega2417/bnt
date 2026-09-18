"""Phylogenetic signal, ancestral states and convergence (Section 4.3)."""

from __future__ import annotations

import numpy as np
import pytest

from evoproto.phylo import (
    Tree,
    ancestral_states,
    blombergs_k,
    c1_significance,
    induce_convergence,
    pagels_lambda,
    random_ultrametric_tree,
    simulate_bm,
    stayton_c1,
    vcv_matrix,
)


def cherry() -> Tree:
    """Two tips joined at depth 0.5 below a root of total depth 1.0."""
    #        root(2)
    #        /     \
    #      t0      node(3)
    #               /   \
    #             t1     t2
    parent = np.array([2, 3, -1, 2])
    branch = np.array([1.0, 0.5, 0.0, 0.5])
    return Tree(parent=parent, branch=branch)


def test_tree_topology_helpers():
    tree = cherry()
    assert tree.root == 2
    assert tree.tips == [0, 1]
    assert tree.n_tips == 2
    assert tree.depth(1) == pytest.approx(1.0)
    assert tree.distance(0, 1) == pytest.approx(2.0)
    assert tree.mrca(0, 1) == 2


def test_vcv_matches_shared_path_lengths():
    tree = cherry()
    C = vcv_matrix(tree)
    assert C[0, 0] == pytest.approx(1.0)
    assert C[1, 1] == pytest.approx(1.0)
    assert C[0, 1] == pytest.approx(0.0)      # they share only the root


def test_vcv_of_a_random_tree_is_psd_and_ultrametric():
    tree = random_ultrametric_tree(12, seed=1)
    C = vcv_matrix(tree)
    assert np.allclose(C, C.T)
    assert np.min(np.linalg.eigvalsh(C)) > -1e-9
    assert np.allclose(np.diag(C), np.diag(C)[0])   # ultrametric: equal tip depths


def test_blombergs_k_has_unit_expectation_under_bm():
    tree = random_ultrametric_tree(16, seed=7)
    values = [blombergs_k(tree, simulate_bm(tree, seed=s)[tree.tips]) for s in range(200)]
    assert np.mean(values) == pytest.approx(1.0, rel=0.25)


def test_blombergs_k_rises_when_relatives_are_forced_alike():
    tree = random_ultrametric_tree(16, seed=7)
    x = simulate_bm(tree, seed=11)[tree.tips]
    noise = np.random.default_rng(0).normal(0, np.std(x) * 3, len(x))
    assert blombergs_k(tree, x) > blombergs_k(tree, x + noise)


def test_pagels_lambda_is_high_for_bm_and_low_for_noise():
    tree = random_ultrametric_tree(20, seed=5)
    bm = simulate_bm(tree, seed=2)[tree.tips]
    lam_bm, lambdas, loglik = pagels_lambda(tree, bm)
    assert 0.0 <= lam_bm <= 1.0
    assert loglik[int(np.argmax(loglik))] == pytest.approx(np.max(loglik))
    noise = np.random.default_rng(4).normal(0, 1, tree.n_tips)
    assert pagels_lambda(tree, noise)[0] <= lam_bm


def test_ancestral_states_keep_tips_and_interpolate_ancestors():
    tree = cherry()
    x = np.array([0.0, 2.0])
    states = ancestral_states(tree, x)
    assert states[0] == pytest.approx(0.0)
    assert states[1] == pytest.approx(2.0)
    assert 0.0 <= states[tree.root] <= 2.0


def test_c1_is_zero_without_convergence_and_high_with_it():
    tree = random_ultrametric_tree(18, seed=20260918)
    x, (a, b) = induce_convergence(tree, seed=20260918)
    converged = stayton_c1(tree, x, a, b)
    assert converged > 0.9              # the two tips were pushed onto one value

    plain = simulate_bm(tree, seed=3)[tree.tips]
    assert stayton_c1(tree, plain, a, b) < converged


def test_c1_significance_rejects_the_brownian_null_for_induced_convergence():
    tree = random_ultrametric_tree(14, seed=3)
    x, (a, b) = induce_convergence(tree, seed=3)
    result = c1_significance(tree, x, a, b, n_sim=200, seed=1)
    assert 0.0 < result["p_value"] <= 1.0
    assert result["c1"] == pytest.approx(stayton_c1(tree, x, a, b))
    assert result["p_value"] < 0.2      # convergence is detectable, as designed


def test_tree_validation():
    with pytest.raises(ValueError):
        Tree(parent=np.array([-1, -1]), branch=np.array([0.0, 1.0]))
    with pytest.raises(ValueError):
        Tree(parent=np.array([-1, 0]), branch=np.array([0.0, -1.0]))
