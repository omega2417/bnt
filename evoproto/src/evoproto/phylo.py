"""Phylogenetic context: signal, convergence and independence (Section 4.3).

The module supplies the four quantities the framework needs from comparative
biology, in a dependency-light form:

* the Brownian-motion variance-covariance matrix ``C`` of a tree and simulation
  of traits on it;
* Blomberg's ``K`` (Eq. 5) and Pagel's ``lambda`` by profile likelihood (Eq. 6),
  which answer the engineering question "is this trait inherited or selected?";
* maximum-likelihood ancestral states under Brownian motion, needed by
* Stayton's ``C1`` (Eq. 7) and its Brownian null significance test (Eq. A.2),
  which decides whether a ``convergentWith`` edge may be inserted at all.

Production deployments are expected to replace these with ape [35] or
phytools [36]; the implementations here exist so that the protocol code is
executable and auditable without an R installation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "Tree",
    "ancestral_states",
    "blombergs_k",
    "c1_significance",
    "pagels_lambda",
    "random_ultrametric_tree",
    "simulate_bm",
    "stayton_c1",
    "vcv_matrix",
]


@dataclass
class Tree:
    """A rooted phylogeny with branch lengths.

    Nodes are integers ``0 .. n_nodes-1``; ``parent[i]`` is the parent of node
    ``i`` and ``-1`` for the root; ``branch[i]`` is the length of the branch
    subtending node ``i`` (``0`` for the root).  Tips are the nodes without
    children, in the order given by :attr:`tips`.
    """

    parent: np.ndarray
    branch: np.ndarray
    labels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.parent = np.asarray(self.parent, dtype=int)
        self.branch = np.asarray(self.branch, dtype=float)
        if self.parent.shape != self.branch.shape:
            raise ValueError("parent and branch must have the same length")
        if np.count_nonzero(self.parent < 0) != 1:
            raise ValueError("a rooted tree has exactly one root")
        if np.any(self.branch < 0):
            raise ValueError("branch lengths must be non-negative")
        if not self.labels:
            self.labels = [f"t{i}" for i in range(self.n_nodes)]
        elif len(self.labels) != self.n_nodes:
            raise ValueError("labels must cover every node")

    @property
    def n_nodes(self) -> int:
        return int(self.parent.size)

    @property
    def root(self) -> int:
        return int(np.flatnonzero(self.parent < 0)[0])

    @property
    def tips(self) -> list[int]:
        """Nodes without children, in ascending index order."""
        has_child = {int(p) for p in self.parent if p >= 0}
        return [i for i in range(self.n_nodes) if i not in has_child]

    @property
    def n_tips(self) -> int:
        return len(self.tips)

    def children(self, node: int) -> list[int]:
        return [i for i in range(self.n_nodes) if self.parent[i] == node]

    def path_to_root(self, node: int) -> list[int]:
        """Node indices from ``node`` up to and including the root."""
        path = [int(node)]
        while self.parent[path[-1]] >= 0:
            path.append(int(self.parent[path[-1]]))
        return path

    def mrca(self, a: int, b: int) -> int:
        """Most recent common ancestor of two nodes."""
        ancestors = self.path_to_root(a)
        seen = set(ancestors)
        for node in self.path_to_root(b):
            if node in seen:
                return node
        raise ValueError("nodes are not in the same tree")

    def depth(self, node: int) -> float:
        """Root-to-node path length."""
        total = 0.0
        current = int(node)
        while self.parent[current] >= 0:
            total += float(self.branch[current])
            current = int(self.parent[current])
        return total

    def distance(self, a: int, b: int) -> float:
        """Patristic distance between two nodes."""
        anc = self.mrca(a, b)
        return self.depth(a) + self.depth(b) - 2.0 * self.depth(anc)

    def distance_matrix(self, nodes: Sequence[int] | None = None) -> np.ndarray:
        idx = list(range(self.n_nodes)) if nodes is None else list(nodes)
        n = len(idx)
        out = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                d = self.distance(idx[i], idx[j])
                out[i, j] = out[j, i] = d
        return out


def random_ultrametric_tree(n_tips: int, seed: int | None = None,
                            total_depth: float = 1.0) -> Tree:
    """Random ultrametric tree by a coalescent-style joining process.

    Tips are joined in random pairs at exponentially spaced heights, so all
    tips end at the same distance from the root - the setting in which
    Blomberg's ``K`` has expectation 1 under Brownian motion (Appendix A.1).
    """
    if n_tips < 2:
        raise ValueError("a tree needs at least two tips")
    rng = np.random.default_rng(seed)
    n_nodes = 2 * n_tips - 1
    parent = np.full(n_nodes, -1, dtype=int)
    height = np.zeros(n_nodes)
    active = list(range(n_tips))
    next_node = n_tips
    time = 0.0
    while len(active) > 1:
        k = len(active)
        time += float(rng.exponential(1.0 / (k * (k - 1) / 2.0)))
        i, j = rng.choice(len(active), size=2, replace=False)
        a, b = active[int(i)], active[int(j)]
        parent[a] = parent[b] = next_node
        height[next_node] = time
        active = [x for x in active if x not in (a, b)] + [next_node]
        next_node += 1
    root = next_node - 1
    scale = total_depth / height[root] if height[root] > 0 else 1.0
    height *= scale
    branch = np.zeros(n_nodes)
    for node in range(n_nodes):
        if parent[node] >= 0:
            branch[node] = height[parent[node]] - height[node]
    labels = [f"tip{i}" for i in range(n_tips)] + [
        f"node{i}" for i in range(n_tips, n_nodes)
    ]
    return Tree(parent=parent, branch=branch, labels=labels)


def vcv_matrix(tree: Tree, nodes: Sequence[int] | None = None,
               reference: int | None = None) -> np.ndarray:
    """Brownian-motion variance-covariance matrix ``C`` (Section 4.3).

    ``C[i, j]`` is the shared branch length from ``reference`` (the root by
    default) to the most recent common ancestor of ``i`` and ``j``, computed as

    .. math:: C_{ij} = \\tfrac{1}{2}\\bigl(d(k,i) + d(k,j) - d(i,j)\\bigr)

    with ``k = reference``.  Writing it through patristic distances makes the
    same routine usable for a tree rerooted at any node, which is what
    :func:`ancestral_states` needs.
    """
    idx = tree.tips if nodes is None else list(nodes)
    k = tree.root if reference is None else int(reference)
    n = len(idx)
    dk = np.array([tree.distance(k, i) for i in idx])
    out = np.empty((n, n))
    for i in range(n):
        for j in range(n):
            dij = 0.0 if i == j else tree.distance(idx[i], idx[j])
            out[i, j] = 0.5 * (dk[i] + dk[j] - dij)
    return np.maximum(out, 0.0)


def simulate_bm(tree: Tree, sigma2: float = 1.0, seed: int | None = None,
                root_state: float = 0.0) -> np.ndarray:
    """Simulate one Brownian-motion trait history over every node of ``tree``.

    Returns the value at each node; ``values[tree.tips]`` are the tip states.
    """
    rng = np.random.default_rng(seed)
    values = np.full(tree.n_nodes, np.nan)
    values[tree.root] = float(root_state)
    order = sorted(range(tree.n_nodes), key=tree.depth)
    for node in order:
        p = int(tree.parent[node])
        if p < 0:
            continue
        values[node] = values[p] + rng.normal(0.0, np.sqrt(sigma2 * tree.branch[node]))
    return values


def _phylogenetic_mean(x: np.ndarray, C: np.ndarray) -> tuple[float, np.ndarray]:
    """GLS root state ``a`` and ``C^-1`` (Section 4.3)."""
    Cinv = np.linalg.pinv(C)
    ones = np.ones(len(x))
    denom = float(ones @ Cinv @ ones)
    a = float(ones @ Cinv @ x) / denom if denom != 0 else float(np.mean(x))
    return a, Cinv


def blombergs_k(tree: Tree, x: Sequence[float]) -> float:
    """Blomberg's ``K`` (Eq. 5).

    ``K`` compares the observed ratio of mean squared error under the star
    phylogeny to that under the tree, normalized by the ratio expected under
    Brownian motion (Eq. A.1).  ``K ~ 1`` means the trait varies as Brownian
    inheritance predicts, ``K > 1`` that close relatives are more alike than
    that - so the trait's presence in a lineage is weak evidence of selection
    for the target function.
    """
    x = np.asarray(x, dtype=float)
    C = vcv_matrix(tree)
    n = len(x)
    if len(x) != C.shape[0]:
        raise ValueError("trait vector must have one entry per tip")
    a, Cinv = _phylogenetic_mean(x, C)
    d = x - a
    mse0 = float(d @ d) / (n - 1)
    mse = float(d @ Cinv @ d) / (n - 1)
    expected = (np.trace(C) - n / float(np.sum(Cinv))) / (n - 1)
    if mse <= 0 or expected <= 0:
        return float("nan")
    return float((mse0 / mse) / expected)


def _lambda_transform(C: np.ndarray, lam: float) -> np.ndarray:
    out = C * lam
    np.fill_diagonal(out, np.diag(C))
    return out


def _bm_loglik(x: np.ndarray, C: np.ndarray) -> float:
    n = len(x)
    a, Cinv = _phylogenetic_mean(x, C)
    d = x - a
    sigma2 = float(d @ Cinv @ d) / n
    sign, logdet = np.linalg.slogdet(C)
    if sigma2 <= 0 or sign <= 0:
        return -np.inf
    return float(-0.5 * (n * np.log(2 * np.pi * sigma2) + logdet + n))


def pagels_lambda(
    tree: Tree, x: Sequence[float], grid: int = 201
) -> tuple[float, np.ndarray, np.ndarray]:
    """Pagel's ``lambda`` by profile likelihood (Eq. 6).

    ``lambda`` scales the off-diagonal covariances of ``C`` and is estimated by
    maximizing the Brownian log-likelihood over a grid on ``[0, 1]``.

    Returns
    -------
    (lambda_hat, lambdas, loglik)
        The maximum-likelihood estimate and the profile used to find it, so
        that the profile can be plotted (Fig. 3c) rather than merely reported.
    """
    x = np.asarray(x, dtype=float)
    C = vcv_matrix(tree)
    lambdas = np.linspace(0.0, 1.0, int(grid))
    loglik = np.array([_bm_loglik(x, _lambda_transform(C, lam)) for lam in lambdas])
    lam_hat = float(lambdas[int(np.argmax(loglik))])
    return lam_hat, lambdas, loglik


def ancestral_states(tree: Tree, x: Sequence[float]) -> np.ndarray:
    """Maximum-likelihood ancestral states under Brownian motion.

    The ML state at an internal node ``k`` is the GLS mean of the tip data with
    respect to the tree rerooted at ``k``; :func:`vcv_matrix` accepts the
    reference node, so the estimate is one linear solve per internal node.

    Reconstructed states are model outputs: any record derived from them must
    carry ``reconstructed=True`` (Section 3.2) and is down-weighted by Eq. (13).
    """
    x = np.asarray(x, dtype=float)
    tips = tree.tips
    if len(x) != len(tips):
        raise ValueError("trait vector must have one entry per tip")
    out = np.full(tree.n_nodes, np.nan)
    for tip_index, node in enumerate(tips):
        out[node] = x[tip_index]
    for node in range(tree.n_nodes):
        if node in tips:
            continue
        C = vcv_matrix(tree, nodes=tips, reference=node)
        out[node] = _phylogenetic_mean(x, C)[0]
    return out


def stayton_c1(tree: Tree, x: Sequence[float], tip_a: int, tip_b: int) -> float:
    """Stayton's ``C1`` convergence measure for a focal tip pair (Eq. 7).

    ``C1 = 1 - D_tip / D_max``, where ``D_tip`` is the phenotypic distance
    between the two tips and ``D_max`` the largest distance between any pair of
    (reconstructed) phenotypes taken from the two lineages back to their common
    ancestor.  ``C1`` is the fraction of ancestral divergence closed by
    subsequent evolution: it is 0 when the tips are as different as their
    lineages ever were, and approaches 1 when two lineages that diverged widely
    have converged on the same phenotype.
    """
    states = ancestral_states(tree, x)
    anc = tree.mrca(tip_a, tip_b)
    path_a = [n for n in tree.path_to_root(tip_a) if tree.depth(n) >= tree.depth(anc)]
    path_b = [n for n in tree.path_to_root(tip_b) if tree.depth(n) >= tree.depth(anc)]
    d_tip = abs(float(states[tip_a]) - float(states[tip_b]))
    d_max = max(
        abs(float(states[a]) - float(states[b])) for a in path_a for b in path_b
    )
    if d_max <= 0:
        return 0.0
    return float(1.0 - d_tip / d_max)


def c1_significance(
    tree: Tree,
    x: Sequence[float],
    tip_a: int,
    tip_b: int,
    n_sim: int = 500,
    seed: int | None = None,
) -> dict[str, float]:
    """Brownian-null significance of ``C1`` (Appendix A.2).

    ``n_sim`` trait histories are simulated on the same tree with the rate
    estimated from the observed data; ancestral states are reconstructed by the
    same method as for the observed data; and ``C1`` is recomputed for the
    focal pair in each simulation.  The empirical p-value is

    .. math:: p = \\frac{1 + \\#\\{C_1^{sim} \\ge C_1^{obs}\\}}{1 + n_{sim}}

    A ``convergentWith`` edge is inserted only when ``p <= alpha`` (corpus
    level, default 0.05) and the tips are not in the same homology class.
    """
    x = np.asarray(x, dtype=float)
    observed = stayton_c1(tree, x, tip_a, tip_b)
    C = vcv_matrix(tree)
    a, Cinv = _phylogenetic_mean(x, C)
    d = x - a
    sigma2 = max(float(d @ Cinv @ d) / len(x), 1e-12)
    rng = np.random.default_rng(seed)
    tips = tree.tips
    exceed = 0
    sims = np.empty(n_sim)
    for i in range(int(n_sim)):
        values = simulate_bm(tree, sigma2=sigma2, seed=int(rng.integers(0, 2**31 - 1)))
        sims[i] = stayton_c1(tree, values[tips], tip_a, tip_b)
        exceed += int(sims[i] >= observed)
    return {
        "c1": observed,
        "p_value": float((1 + exceed) / (1 + n_sim)),
        "null_mean": float(np.mean(sims)),
        "null_sd": float(np.std(sims, ddof=1)) if n_sim > 1 else float("nan"),
        "n_sim": float(n_sim),
        "sigma2": sigma2,
    }


def induce_convergence(
    tree: Tree,
    seed: int | None = None,
    sigma2: float = 1.0,
    shift: float = 2.5,
) -> tuple[np.ndarray, tuple[int, int]]:
    """SYNTHETIC helper: a Brownian trait with a convergent shift in two tips.

    Used by Fig. 3 and by the tests.  Two of the most distantly related tips
    are pushed towards a common value, which is exactly the pattern ``C1`` is
    meant to detect.  The returned data are SYNTHETIC and support no claim.
    """
    rng = np.random.default_rng(seed)
    values = simulate_bm(tree, sigma2=sigma2, seed=int(rng.integers(0, 2**31 - 1)))
    tips = tree.tips
    x = values[tips].copy()
    distances = tree.distance_matrix(tips)
    i, j = np.unravel_index(int(np.argmax(distances)), distances.shape)
    target = float(np.max(x)) + shift
    x[i] = x[j] = target
    return x, (tips[int(i)], tips[int(j)])
