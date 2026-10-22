"""Detection metrics. Precision-recall measures follow Saito & Rehmsmeier
(2015), doi:10.1371/journal.pone.0118432."""
from __future__ import annotations

import math
import statistics
from typing import Sequence


def confusion(labels: Sequence[int], preds: Sequence[bool]) -> dict[str, int]:
    tp = sum(1 for y, p in zip(labels, preds) if y and p)
    fp = sum(1 for y, p in zip(labels, preds) if not y and p)
    fn = sum(1 for y, p in zip(labels, preds) if y and not p)
    tn = sum(1 for y, p in zip(labels, preds) if not y and not p)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def prf(c: dict[str, int]) -> dict[str, float]:
    tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fp_per_1000 = 1000.0 * fp / (fp + tn) if fp + tn else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "fp_per_1000_normal": fp_per_1000}


def average_precision(labels: Sequence[int], scores: Sequence[float | None]) -> float:
    """Step-wise area under the precision-recall curve (AUPRC).

    Missing or NaN scores (events that were never scored) rank last.
    """
    pos = sum(labels)
    if pos == 0:
        return float("nan")
    clean = [-math.inf if s is None or math.isnan(s) else float(s) for s in scores]
    order = sorted(range(len(clean)), key=lambda i: -clean[i])
    tp = fp = 0
    ap = 0.0
    i = 0
    while i < len(order):
        j = i
        s = clean[order[i]]
        new_tp = 0
        while j < len(order) and (j == i or clean[order[j]] == s):
            if labels[order[j]]:
                new_tp += 1
            else:
                fp += 1
            j += 1
        tp += new_tp
        ap += (new_tp / pos) * (tp / (tp + fp))
        i = j
    return ap


def mean_sd(values: Sequence[float]) -> tuple[float, float]:
    vals = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return float("nan"), float("nan")
    m = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return m, sd
