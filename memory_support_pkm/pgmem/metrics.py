"""Evaluation indicators (Section 6, Equations 6 and 7)."""
from __future__ import annotations

import math


def _ratio(num: float, den: float) -> float:
    return num / den if den else math.nan


def tsr(n_completed: int, n_scheduled: int) -> float:
    """Task success rate TSR = N_c / N_s."""
    return _ratio(n_completed, n_scheduled)


def fpr(n_false_prompts: int, n_prompts: int) -> float:
    """False-prompt rate FPR = N_f / N_p."""
    return _ratio(n_false_prompts, n_prompts)


def f_ext(n_supported: int, n_released: int) -> float:
    """Externally assessed recall faithfulness F_ext = N_e / N_r.
    Undefined (NaN) when no claim is released — never reported as perfect."""
    return _ratio(n_supported, n_released)


def coverage(n_substantive: int, n_questions: int) -> float:
    """Answer coverage C = N_a / N_q."""
    return _ratio(n_substantive, n_questions)


def independence_index(n_completed_l0_l1: int, n_completed: int) -> float:
    """Share of completions achieved at L0-L1."""
    return _ratio(n_completed_l0_l1, n_completed)


def per_100(n_events: int, n_answers: int) -> float:
    """E.g. fabricated recollections per 100 substantive answers."""
    return 100.0 * _ratio(n_events, n_answers)
