"""Phylogenetic context: signal, convergence and independence (Section 4.3).

Implements, on a lightweight tree object so that the package stays
dependency-light:

* the Brownian-motion variance-covariance matrix ``C`` of a tree;
* Eq. (5)   Blomberg's K;
* Eq. (6)   Pagel's lambda by profile likelihood;
* Eq. (7)   Stayton's C1 between two focal tips;
* Eq. (A.2) the Brownian-motion simulation p-value of C1;
* maximum-likelihood ancestral state reconstruction under Brownian motion
  (the two-pass pruning algorithm), which C1 needs.

Production use is expected to substitute ``ape`` or ``phytools``; these
implementations exist so that the protocol code runs without an R bridge, and
they are unit-tested against the analytic results of Appendix A.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "Tree",
    "random_ultrametric_tree",
    "vcv_matrix",
    "simulate_brownian",
    "pgls_root",
    "blombergs_k",
    "expected_k_denominator",
    "pagels_lambda",
    "lambda_profile",
    "ancestral_states",
    "stayton_c1",
    "c1_pvalue",
]


@dataclass
class Tree:
    """A rooted tree with branch lengths.

    Nodes are integers ``0..n_nodes-1``; ``parent[root] == -1``.  Tips are the
    nodes without children.  ``labels`` names the tips.
    """

    parent: np.ndarray
    branch_length: np.ndarray
    labels: Dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.parent = np.asarray(self.parent, dtype=int)
        self.branch_length = np.asarray(self.branch_length, dtype=float)
        if self.parent.shape != self.branch_length.shape:
            raise ValueError("parent and branch_length must have the same length")
        if int(np.sum(self.parent < 0)) != 1:
            raise ValueError("a tree must have exactly one root")

    # ------------------------------------------------------------- topology
    @property
    def n_nodes(self) -> int:
        return int(self.parent.size)

    @property
    def root(self) -> int:
        return int(np.flatnonzero(self.parent < 0)[0])

    @property
    def children(self) -> Dict[int, List[int]]:
        out: Dict[int, List[int]] = {i: [] for i in range(self.n_nodes)}
        for node, par in enumerate(self.parent):
            if par >= 0:
                out[int(par)].append(node)
        return out

    @property
    def tips(self) -> List[int]:
        kids = self.children
        return [i for i in range(self.n_nodes) if not kids[i]]

    @property
    def n_tips(self) -> int:
        return len(self.tips)

    def tip_index(self, label: str) -> int:
        for node, name in self.labels.items():
            if name == label:
                return node
        raise KeyError(f"unknown tip label {label!r}")

    def path_to_root(self, node: int) -> List[int]:
        """Nodes from ``node`` up to the root, inclusive."""
        path = [int(node)]
        while self.parent[path[-1]] >= 0:
            path.append(int(self.parent[path[-1]]))
        return path

    def mrca(self, a: int, b: int) -> int:
        """Most recent common ancestor of two nodes."""
        ancestors = set(self.path_to_root(a))
        for node in self.path_to_root(b):
            if node in ancestors:
                return node
        raise ValueError("nodes do not share a root")

    def depth(self, node: int) -> float:
        """Distance from the root to ``node`` along branches."""
        total = 0.0
        current = int(node)
        while self.parent[current] >= 0:
            total += float(self.branch_length[current])
            current = int(self.parent[current])
        return total

    def postorder(self) -> List[int]:
        kids = self.children
        order: List[int] = []
        stack = [(self.root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            stack.append((node, True))
            for child in kids[node]:
                stack.append((child, False))
        return order

    def preorder(self) -> List[int]:
        return list(reversed(self.postorder()))


def random_ultrametric_tree(n_tips: int, seed: int = 0, total_depth: float = 1.0) -> Tree:
    """A random ultrametric tree by a Yule-style coalescent (Fig. 3a).

    Lineages are merged in random pairs at exponentially spaced heights; every
    tip ends at ``total_depth`` from the root, which is what the Brownian-motion
    null of Appendix A assumes.
    """
    if n_tips < 2:
        raise ValueError("a tree needs at least two tips")
    rng = np.random.default_rng(seed)
    n_nodes = 2 * n_tips - 1
    parent = np.full(n_nodes, -1, dtype=int)
    height = np.zeros(n_nodes)  # height above the present (tips at 0)
    active = list(range(n_tips))
    next_node = n_tips
    current_height = 0.0
    while len(active) > 1:
        k = len(active)
        current_height += float(rng.exponential(1.0 / (k * (k - 1) / 2)))
        i, j = rng.choice(len(active), size=2, replace=False)
        a, b = active[int(i)], active[int(j)]
        parent[a] = parent[b] = next_node
        height[next_node] = current_height
        active = [x for x in active if x not in (a, b)] + [next_node]
        next_node += 1
    scale = total_depth / current_height if current_height > 0 else 1.0
    height *= scale
    branch = np.zeros(n_nodes)
    for node in range(n_nodes):
        par = parent[node]
        if par >= 0:
            branch[node] = height[par] - height[node]
    labels = {i: f"t{i}" for i in range(n_tips)}
    return Tree(parent=parent, branch_length=branch, labels=labels)


def vcv_matrix(tree: Tree) -> np.ndarray:
    r"""Brownian-motion variance-covariance matrix ``C``.

    ``C_ij`` is the shared branch length from the root to the most recent
    common ancestor of tips ``i`` and ``j`` (Section 4.3).
    """
    tips = tree.tips
    n = len(tips)
    C = np.zeros((n, n))
    depths = {node: tree.depth(node) for node in range(tree.n_nodes)}
    for a in range(n):
        for b in range(a, n):
            shared = depths[tree.mrca(tips[a], tips[b])]
            C[a, b] = C[b, a] = shared
    return C


def simulate_brownian(
    tree: Tree,
    sigma2: float = 1.0,
    seed: int = 0,
    root_state: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Simulate a Brownian-motion trait on ``tree``.

    Returns ``(tip_values, node_values)``: the trait at the tips in tip order,
    and the true trait at every node (used to check the reconstruction).
    """
    rng = np.random.default_rng(seed)
    values = np.zeros(tree.n_nodes)
    values[tree.root] = root_state
    for node in tree.preorder():
        par = tree.parent[node]
        if par >= 0:
            sd = float(np.sqrt(sigma2 * tree.branch_length[node]))
            values[node] = values[par] + rng.normal(0.0, sd)
    tips = tree.tips
    return values[tips], values


def pgls_root(x: np.ndarray, C: np.ndarray) -> float:
    r"""Phylogenetic generalised-least-squares mean :math:`\hat a`.

    :math:`\hat a = (\mathbf 1^\top C^{-1}\mathbf 1)^{-1}\mathbf 1^\top C^{-1}\mathbf x`.
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    ones = np.ones_like(x)
    Cinv_ones = np.linalg.solve(C, ones)
    return float(ones @ np.linalg.solve(C, x) / (ones @ Cinv_ones))


def expected_k_denominator(C: np.ndarray) -> float:
    r"""Eq. (A.1): :math:`\frac{1}{n-1}\left[\mathrm{tr}(C) - n/(\mathbf 1^\top C^{-1}\mathbf 1)\right]`."""
    n = C.shape[0]
    ones = np.ones(n)
    return float((np.trace(C) - n / (ones @ np.linalg.solve(C, ones))) / (n - 1))


def blombergs_k(x: np.ndarray, C: np.ndarray) -> float:
    r"""Eq. (5): Blomberg's K.

    :math:`K = \dfrac{(\mathbf x-\hat a\mathbf 1)^\top(\mathbf x-\hat a\mathbf 1)
    / (\mathbf x-\hat a\mathbf 1)^\top C^{-1}(\mathbf x-\hat a\mathbf 1)}
    {\frac{1}{n-1}[\mathrm{tr}(C)-n/(\mathbf 1^\top C^{-1}\mathbf 1)]}`

    ``K = 1`` is the expectation under Brownian motion on the given tree
    (Appendix A.1); ``K > 1`` means more phylogenetic signal than Brownian
    motion predicts, i.e. the trait is largely inherited.
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    a_hat = pgls_root(x, C)
    resid = x - a_hat
    mse0 = float(resid @ resid)
    mse = float(resid @ np.linalg.solve(C, resid))
    if mse <= 0:
        raise ValueError("degenerate trait vector: phylogenetic MSE is zero")
    return float((mse0 / mse) / expected_k_denominator(C))


def _lambda_matrix(C: np.ndarray, lam: float) -> np.ndarray:
    """``C_lambda``: off-diagonal covariances scaled by ``lambda`` (Eq. 6)."""
    C_lam = lam * C.copy()
    np.fill_diagonal(C_lam, np.diag(C))
    return C_lam


def _lambda_loglik(x: np.ndarray, C: np.ndarray, lam: float) -> float:
    r"""Profile log-likelihood :math:`\ell(\lambda)` of Eq. (6)."""
    n = x.size
    C_lam = _lambda_matrix(C, lam)
    sign, logdet = np.linalg.slogdet(C_lam)
    if sign <= 0:
        return -np.inf
    a_hat = pgls_root(x, C_lam)
    resid = x - a_hat
    sigma2 = float(resid @ np.linalg.solve(C_lam, resid) / n)
    if sigma2 <= 0:
        return -np.inf
    return float(-0.5 * (n * np.log(2.0 * np.pi * sigma2) + logdet + n))


def lambda_profile(
    x: np.ndarray,
    C: np.ndarray,
    grid: Optional[Sequence[float]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Profile log-likelihood of Pagel's lambda over a grid (Fig. 3c)."""
    x = np.asarray(x, dtype=float).reshape(-1)
    lambdas = np.asarray(grid if grid is not None else np.linspace(0.0, 1.0, 101), dtype=float)
    ll = np.array([_lambda_loglik(x, C, float(lam)) for lam in lambdas])
    return lambdas, ll


def pagels_lambda(x: np.ndarray, C: np.ndarray, tol: float = 1e-6) -> float:
    r"""Eq. (6): maximum-likelihood Pagel's :math:`\lambda \in [0, 1]`.

    Maximised by golden-section search on the profile likelihood, with the
    boundaries checked explicitly (the maximum is frequently at 0 or 1).
    """
    x = np.asarray(x, dtype=float).reshape(-1)

    def nll(lam: float) -> float:
        return -_lambda_loglik(x, C, lam)

    lo, hi = 0.0, 1.0
    invphi = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - invphi * (b - a), a + invphi * (b - a)
    fc, fd = nll(c), nll(d)
    while abs(b - a) > tol:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - invphi * (b - a)
            fc = nll(c)
        else:
            a, c, fc = c, d, fd
            d = a + invphi * (b - a)
            fd = nll(d)
    interior = 0.5 * (a + b)
    candidates = [(nll(lo), lo), (nll(hi), hi), (nll(interior), interior)]
    return float(min(candidates)[1])


def ancestral_states(tree: Tree, tip_values: Sequence[float]) -> np.ndarray:
    """Maximum-likelihood ancestral states under Brownian motion.

    Two-pass pruning: a post-order pass gives each internal node the estimate
    and variance implied by its descendants, and a pre-order pass combines that
    with the information coming from the rest of the tree.  Returns the trait
    value of every node (tips keep their observed value).

    Reconstructed states are model outputs: records built from them carry
    ``r = 1`` and are down-weighted by Eq. (13).
    """
    tip_values = np.asarray(tip_values, dtype=float).reshape(-1)
    tips = tree.tips
    if tip_values.size != len(tips):
        raise ValueError("tip_values must have one entry per tip")

    n = tree.n_nodes
    kids = tree.children
    mu = np.full(n, np.nan)
    var = np.full(n, np.inf)
    for tip, value in zip(tips, tip_values):
        mu[tip], var[tip] = float(value), 0.0

    # Post-order: combine children, each seen through its own branch.
    for node in tree.postorder():
        if not kids[node]:
            continue
        weights, means = [], []
        for child in kids[node]:
            v = var[child] + float(tree.branch_length[child])
            weights.append(1.0 / v if v > 0 else np.inf)
            means.append(mu[child])
        w = np.asarray(weights, dtype=float)
        m = np.asarray(means, dtype=float)
        var[node] = 1.0 / float(np.sum(w))
        mu[node] = float(np.sum(w * m) / np.sum(w))

    # Pre-order: add the information coming from outside each subtree.
    # up_mu[v] / up_var[v] describe v's state as implied by everything that is
    # not in v's subtree; the root has no such information.
    up_mu = np.full(n, np.nan)
    up_var = np.full(n, np.inf)
    out = mu.copy()
    for node in tree.preorder():
        if node == tree.root:
            out[node] = mu[node]
            continue
        par = int(tree.parent[node])
        weights, means = [], []
        if par != tree.root and np.isfinite(up_var[par]) and up_var[par] > 0:
            weights.append(1.0 / up_var[par])
            means.append(up_mu[par])
        for sibling in kids[par]:
            if sibling == node:
                continue
            v = var[sibling] + float(tree.branch_length[sibling])
            weights.append(1.0 / v)
            means.append(mu[sibling])
        if weights:
            w = np.asarray(weights, dtype=float)
            m = np.asarray(means, dtype=float)
            par_var = 1.0 / float(np.sum(w))
            par_mu = float(np.sum(w * m) / np.sum(w))
        else:  # the parent carries no information beyond this child
            par_var, par_mu = np.inf, mu[par]
        up_var[node] = par_var + float(tree.branch_length[node])
        up_mu[node] = par_mu
        if kids[node] and np.isfinite(up_var[node]):
            w_down = 1.0 / var[node] if var[node] > 0 else np.inf
            w_up = 1.0 / up_var[node]
            out[node] = float((w_down * mu[node] + w_up * up_mu[node]) / (w_down + w_up))
    for tip, value in zip(tips, tip_values):
        out[tip] = float(value)
    return out


def _lineage_ancestors(tree: Tree, tip: int, mrca: int) -> List[int]:
    """Nodes on the path from ``tip`` up to and including ``mrca``."""
    path = []
    current = int(tip)
    while True:
        path.append(current)
        if current == mrca:
            break
        current = int(tree.parent[current])
        if current < 0:
            raise ValueError("mrca is not an ancestor of tip")
    return path


def stayton_c1(
    tree: Tree,
    tip_values: Sequence[float],
    tip_i: int,
    tip_j: int,
    states: Optional[np.ndarray] = None,
) -> float:
    r"""Eq. (7): Stayton's :math:`C_1 = 1 - D_{\mathrm{tip}}/D_{\max}`.

    ``D_tip`` is the phenotypic distance between the two focal tips and
    ``D_max`` the largest distance between any pair of points on the two
    lineages back to their common ancestor.  Following Stayton, each lineage
    comprises its reconstructed ancestors *and* its tip, so ``D_max >= D_tip``
    and ``C1`` lies in ``[0, 1]``: ``C1 = 0`` means the tips are at the largest
    distance the two lineages ever reached, i.e. no convergence at all.  ``C1`` is the fraction of
    ancestral divergence that subsequent evolution has closed: 0 means the tips
    are no closer than their ancestors ever were, 1 means they have converged
    completely.
    """
    values = ancestral_states(tree, tip_values) if states is None else np.asarray(states, dtype=float)
    mrca = tree.mrca(tip_i, tip_j)
    A_i = _lineage_ancestors(tree, tip_i, mrca)
    A_j = _lineage_ancestors(tree, tip_j, mrca)
    d_tip = abs(float(values[tip_i]) - float(values[tip_j]))
    d_max = max(abs(float(values[a]) - float(values[b])) for a in A_i for b in A_j)
    if d_max <= 0:
        return 0.0
    return float(1.0 - d_tip / d_max)


def c1_pvalue(
    tree: Tree,
    tip_values: Sequence[float],
    tip_i: int,
    tip_j: int,
    n_sim: int = 500,
    seed: int = 0,
) -> Tuple[float, float, np.ndarray]:
    r"""Eq. (A.2): simulation p-value of :math:`C_1` under Brownian motion.

    ``n_sim`` trait histories are simulated on the same tree with the rate
    estimated from the observed data, ancestral states are reconstructed by the
    same method, and ``C1`` is recomputed for the focal pair.  The p-value is
    :math:`(1+\#\{C_1^{\mathrm{sim}} \ge C_1^{\mathrm{obs}}\})/(1+n_{\mathrm{sim}})`.

    Returns ``(C1_observed, p_value, C1_null_distribution)``.  A
    ``convergentWith`` edge requires ``p <= alpha`` (default 0.05) and
    non-membership in a common homology class.
    """
    tip_values = np.asarray(tip_values, dtype=float).reshape(-1)
    C = vcv_matrix(tree)
    a_hat = pgls_root(tip_values, C)
    resid = tip_values - a_hat
    sigma2 = float(resid @ np.linalg.solve(C, resid) / (tip_values.size - 1))
    observed = stayton_c1(tree, tip_values, tip_i, tip_j)
    null = np.empty(n_sim)
    for s in range(n_sim):
        sim_tips, _ = simulate_brownian(tree, sigma2=max(sigma2, 1e-12), seed=seed + s + 1)
        null[s] = stayton_c1(tree, sim_tips, tip_i, tip_j)
    p = float((1 + int(np.sum(null >= observed))) / (1 + n_sim))
    return observed, p, null
