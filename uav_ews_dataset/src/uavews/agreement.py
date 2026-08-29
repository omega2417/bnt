"""Inter-annotator agreement.

Krippendorff's alpha is used rather than a kappa family because it is the only
common coefficient that handles the three properties this annotation task
actually has: more than two annotators, annotators who did not all see the same
items, and missing judgements. All three are guaranteed here - annotators are
assigned per event, and a rater may abstain when the handbook says the evidence
is insufficient.

    alpha = 1 - D_o / D_e

with D_o the observed disagreement and D_e the disagreement expected from the
marginal distribution alone. The coefficient is reported alongside class
prevalence and the confusion matrix, because a single number cannot distinguish
"raters agree" from "one class dominates", and the manuscript is explicit that it
should not be read on its own.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd


def krippendorff_alpha_nominal(units: Dict[object, Sequence[object]]) -> float:
    """Alpha for nominal data, computed from the coincidence matrix.

    ``units`` maps an item to the judgements it received. Items judged only once
    contribute nothing - a single rating cannot agree or disagree with anything -
    and are excluded, which is the standard treatment and not a data loss.
    """
    values = sorted({v for vs in units.values() for v in vs if v is not None})
    if len(values) < 2:
        return float("nan")
    index = {v: i for i, v in enumerate(values)}
    k = len(values)
    coincidence = np.zeros((k, k), dtype=np.float64)

    for vs in units.values():
        vs = [v for v in vs if v is not None]
        m = len(vs)
        if m < 2:
            continue
        counts = Counter(index[v] for v in vs)
        for a, ca in counts.items():
            for b, cb in counts.items():
                coincidence[a, b] += (ca * (cb - 1) if a == b else ca * cb) / (m - 1)

    n = coincidence.sum()
    if n <= 0:
        return float("nan")
    marginals = coincidence.sum(axis=1)

    observed = n - np.trace(coincidence)
    expected = (n ** 2 - np.sum(marginals ** 2)) / (n - 1) if n > 1 else 0.0
    if expected == 0:
        return float("nan")
    return float(1.0 - observed / expected)


def bootstrap_alpha_ci(units: Dict[object, Sequence[object]], n_boot: int = 400,
                       alpha_level: float = 0.05, seed: int = 7) -> tuple[float, float]:
    """Percentile bootstrap over *units*, not over individual judgements.

    Resampling judgements independently would break the within-unit structure
    that the coefficient is built on, and would produce an interval that is far
    too narrow.
    """
    rng = np.random.default_rng(seed)
    keys = list(units.keys())
    if len(keys) < 3:
        return (float("nan"), float("nan"))
    draws: List[float] = []
    for _ in range(n_boot):
        sample = rng.choice(len(keys), size=len(keys), replace=True)
        sub = {i: units[keys[j]] for i, j in enumerate(sample)}
        a = krippendorff_alpha_nominal(sub)
        if not np.isnan(a):
            draws.append(a)
    if len(draws) < 10:
        return (float("nan"), float("nan"))
    lo = float(np.percentile(draws, 100 * alpha_level / 2))
    hi = float(np.percentile(draws, 100 * (1 - alpha_level / 2)))
    return lo, hi


def confusion(units: Dict[object, Sequence[object]]) -> pd.DataFrame:
    """Pairwise co-judgement counts, which is what alpha actually summarizes."""
    values = sorted({v for vs in units.values() for v in vs if v is not None})
    m = pd.DataFrame(0, index=values, columns=values, dtype=int)
    for vs in units.values():
        vs = [v for v in vs if v is not None]
        for i in range(len(vs)):
            for j in range(len(vs)):
                if i != j:
                    m.loc[vs[i], vs[j]] += 1
    return m


def boundary_agreement(pairs: Iterable[tuple[tuple[int, int], tuple[int, int]]]
                       ) -> Dict[str, float]:
    """Temporal boundary agreement: mean absolute deviation and mean IoU.

    Categorical agreement says nothing about where two annotators placed the
    start and end of an interval, and a model trained on boundaries that disagree
    by seconds will learn the disagreement. Both statistics are reported because
    they fail differently: MAD is unbounded and interpretable in seconds, IoU is
    bounded but collapses for short intervals.
    """
    from . import timebase as tb
    mads: List[float] = []
    ious: List[float] = []
    for a, b in pairs:
        mads.append((abs(a[0] - b[0]) + abs(a[1] - b[1])) / 2.0 / tb.NS)
        ious.append(tb.iou(a, b))
    if not mads:
        return {"n": 0, "boundary_mad_s": float("nan"), "boundary_iou": float("nan")}
    return {"n": len(mads), "boundary_mad_s": float(np.mean(mads)),
            "boundary_iou": float(np.mean(ious))}


def agreement_report(labels: pd.DataFrame, targets: Sequence[str],
                     n_boot: int = 300) -> pd.DataFrame:
    """Per-target alpha with bootstrap interval, prevalence, and rater count."""
    rows: List[dict] = []
    for target in targets:
        sub = labels[(labels["target_name"] == target)
                     & (~labels["is_adjudicated_final"])]
        if sub.empty:
            continue
        units = {tid: list(g["value"]) for tid, g in sub.groupby("target_id")}
        multi = {k: v for k, v in units.items() if len(v) > 1}
        a = krippendorff_alpha_nominal(multi)
        lo, hi = bootstrap_alpha_ci(multi, n_boot=n_boot)
        counts = Counter(v for vs in multi.values() for v in vs)
        total = sum(counts.values()) or 1
        rows.append({
            "target_name": target,
            "n_units": len(multi),
            "n_judgements": total,
            "mean_raters_per_unit": float(np.mean([len(v) for v in multi.values()]))
            if multi else float("nan"),
            "krippendorff_alpha": a,
            "alpha_ci_low": lo, "alpha_ci_high": hi,
            "majority_class": counts.most_common(1)[0][0] if counts else None,
            "majority_prevalence": counts.most_common(1)[0][1] / total if counts else float("nan"),
        })
    return pd.DataFrame(rows)
