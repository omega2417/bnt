"""Graduated assistance (Section 4.3, Equations 2 and 3).

Levels: L0 silent context, L1 brief reminder, L2 contextual cue,
L3 step-by-step guidance, L4 trusted-person involvement.
"""
from __future__ import annotations

LEVEL_NAMES = {
    0: "L0 context, no prompt",
    1: "L1 brief reminder",
    2: "L2 contextual cue",
    3: "L3 step-by-step guidance",
    4: "L4 trusted-person involvement",
}


def gate(permission_ok: bool, postponed: bool, declined: bool, progress_supports_escalation: bool) -> int:
    """Binary gate G_k: 1 only if permission allows another prompt, the user has
    neither postponed nor declined, and the progress check supports escalation.
    Missing/ambiguous observations must yield progress_supports_escalation=False."""
    return int(permission_ok and not postponed and not declined and progress_supports_escalation)


def next_level(level: int, g: int, l_max: int) -> int:
    """Equation (2): L_{k+1} = G_k * min(L_k + 1, L_max) + (1 - G_k) * L_k."""
    return g * min(level + 1, l_max) + (1 - g) * level


def adapt_start_level(start: int, consecutive_without_escalation: int, m: int,
                      l_min: int, user_agrees: bool) -> int:
    """Equation (3): L0(j+1) = max(L0(j) - 1, L_min) after m consecutive
    episodes completed without escalation, and only with the user's agreement."""
    if consecutive_without_escalation >= m and user_agrees:
        return max(start - 1, l_min)
    return start
