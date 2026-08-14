"""Detection, attribution, response and overhead metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    roc_auc_score,
)

from .. import ALL_LABELS

__all__ = [
    "binary_detection_metrics",
    "tune_threshold",
    "attribution_metrics",
    "confusion",
]


def binary_detection_metrics(
    scores: np.ndarray, y_true: np.ndarray, threshold: float
) -> dict[str, float]:
    """Precision/recall/F1/FPR at a threshold, plus threshold-free AUROC/AUPRC."""
    scores = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    pred = (scores >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    out = {
        "precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }
    if len(np.unique(y)) == 2:
        out["auroc"] = float(roc_auc_score(y, scores))
        out["auprc"] = float(average_precision_score(y, scores))
    else:
        out["auroc"] = float("nan")
        out["auprc"] = float("nan")
    return out


def tune_threshold(scores: np.ndarray, y_true: np.ndarray) -> float:
    """Pick the threshold maximising F1 on the (validation) scores."""
    scores = np.asarray(scores, dtype=float)
    y = np.asarray(y_true, dtype=int)
    if len(np.unique(y)) < 2:
        return float(np.median(scores))
    candidates = np.unique(np.quantile(scores, np.linspace(0.01, 0.99, 99)))
    best_thr, best_f1 = candidates[0], -1.0
    for thr in candidates:
        m = binary_detection_metrics(scores, y, thr)
        if m["f1"] > best_f1:
            best_f1, best_thr = m["f1"], float(thr)
    return best_thr


def attribution_metrics(
    y_true_leaf: np.ndarray,
    y_pred_leaf: np.ndarray,
    y_true_macro: np.ndarray,
    y_pred_macro: np.ndarray,
) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, f1_score

    return {
        "leaf_accuracy": float(accuracy_score(y_true_leaf, y_pred_leaf)),
        "macro_accuracy": float(accuracy_score(y_true_macro, y_pred_macro)),
        "macro_f1": float(f1_score(y_true_leaf, y_pred_leaf, average="macro",
                                   labels=list(ALL_LABELS), zero_division=0)),
    }


def confusion(y_true: np.ndarray, y_pred: np.ndarray, labels=ALL_LABELS) -> np.ndarray:
    return confusion_matrix(y_true, y_pred, labels=list(labels))
