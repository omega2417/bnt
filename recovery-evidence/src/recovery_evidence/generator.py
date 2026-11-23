"""Exogenous generator: hidden component states and change notices (Section 4.1).

The generator is the only place where pseudo-random numbers are consumed by
the experiment.  It runs *before* any policy and never sees a policy decision,
so all four policies are replayed on an identical trajectory.

Random-number consumption (fixed; see docs/RNG_STREAMS.md)
---------------------------------------------------------
For configuration ``c``, replicate ``r`` (0-based) and stream ``s`` the bit
generator is ``PCG64(SeedSequence(root_entropy, spawn_key=(c, r, s)))``.
Each stream is consumed in one fixed block, independent of every parameter
except the horizon ``T`` and the number of components ``m``:

====== ======================== ==========================================
stream call(s), in this order   use of element ``[t, j]`` (day t, column j)
====== ======================== ==========================================
0      ``random((T+1, m))``      transition of component j on day t
1      ``random((T+1, m))``      notice generated if ``< p_report``
2      ``integers(0, K, (T+1, m))`` index of the delay of that notice
3      ``random((T+1, m))`` then non-substantive notice if ``< p_nonsub``;
       ``integers(0, K, (T+1, m))`` index of its delay
4      ``random(T+1)``           joint degradation on day t if ``< p_joint``
====== ======================== ==========================================

``K = len(delay_values)``.  Row 0 of every block belongs to day 0 (the audited
initial state) and is never used.  Columns follow the alphabetical component
order of the dependency map.  Because every block is drawn in full, changing
one mechanism (for example ``p_report``) cannot shift the draws of another.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .conditions import Condition

STREAM_TRANSITIONS = 0
STREAM_NOTICES = 1
STREAM_DELAYS = 2
STREAM_NON_SUBSTANTIVE = 3
STREAM_JOINT = 4


@dataclass(frozen=True)
class Notice:
    """One change notice.  ``kind`` and ``new_state`` exist only in the reference log."""

    component: int
    occurred: int
    delivered: int
    kind: str  # "substantive" | "non_substantive"
    new_state: Optional[int]  # None for non-substantive notices
    suppressed: bool  # generated but withheld from the operator (C6)
    beyond_horizon: bool  # delivery day > T


@dataclass(frozen=True)
class Trajectory:
    """Everything exogenous for one (condition, replicate)."""

    condition: str
    replicate: int
    components: Tuple[str, ...]
    states: Tuple[Tuple[int, ...], ...]  # states[t][j], t = 0..T ; states[0] = all capable
    notices: Tuple[Notice, ...]
    joint_days: Tuple[int, ...]

    @property
    def T(self) -> int:
        return len(self.states) - 1

    def operator_feed(self) -> List[List[Tuple[int, int]]]:
        """What the operator may see: per delivery day, (component, occurrence day).

        Suppressed notices and notices delivered after the horizon are absent;
        cause and new state are never included.
        """
        feed: List[List[Tuple[int, int]]] = [[] for _ in range(self.T + 1)]
        for n in self.notices:
            if not n.suppressed and not n.beyond_horizon:
                feed[n.delivered].append((n.component, n.occurred))
        return feed


def stream(root_entropy: int, condition_id: int, replicate: int, stream_id: int) -> np.random.Generator:
    """The PCG64 generator of one (configuration, replicate, stream)."""
    seq = np.random.SeedSequence(root_entropy, spawn_key=(condition_id, replicate, stream_id))
    return np.random.Generator(np.random.PCG64(seq))


def generate(
    cond: Condition,
    replicate: int,
    components: Sequence[str],
    forced_joint_days: Sequence[int] = (),
) -> Trajectory:
    """Generate the hidden trajectory and all notices of one replicate.

    ``forced_joint_days`` is used only by the deterministic implementation
    check of condition C7 (joint failure on a fixed day).
    """
    T, m = cond.T, len(components)
    K = len(cond.delay_values)

    def rng(s: int) -> np.random.Generator:
        return stream(cond.root_entropy, cond.id, replicate, s)

    u_trans = rng(STREAM_TRANSITIONS).random((T + 1, m)).tolist()
    u_report = rng(STREAM_NOTICES).random((T + 1, m)).tolist()
    k_delay = rng(STREAM_DELAYS).integers(0, K, size=(T + 1, m)).tolist()
    g3 = rng(STREAM_NON_SUBSTANTIVE)
    u_nonsub = g3.random((T + 1, m)).tolist()
    k_nonsub = g3.integers(0, K, size=(T + 1, m)).tolist()
    u_joint = rng(STREAM_JOINT).random(T + 1).tolist()

    joint_idx = [components.index(c) for c in cond.joint_components if c in components]
    suppressed = {components.index(c) for c in cond.suppressed_components if c in components}
    forced = set(forced_joint_days)

    states: List[Tuple[int, ...]] = [tuple([1] * m)]
    notices: List[Notice] = []
    joint_days: List[int] = []
    for t in range(1, T + 1):
        start = states[-1]
        row_u = u_trans[t]
        # ordinary two-state Markov transition of every component
        end = [
            (0 if row_u[j] < cond.p_fail else 1) if start[j] == 1
            else (1 if row_u[j] < cond.p_rec else 0)
            for j in range(m)
        ]
        # joint degradation of the redundant pair, applied after ordinary transitions
        if (cond.p_joint > 0.0 and u_joint[t] < cond.p_joint) or t in forced:
            joint_days.append(t)
            for j in joint_idx:
                end[j] = 0
        states.append(tuple(end))
        # notices: a change is counted by comparing the start and the end of the step
        for j in range(m):
            if end[j] != start[j]:
                if u_report[t][j] < cond.p_report:
                    delivered = t + cond.delay_values[k_delay[t][j]]
                    notices.append(Notice(j, t, delivered, "substantive", end[j], j in suppressed, delivered > T))
            elif u_nonsub[t][j] < cond.p_nonsubstantive:
                delivered = t + cond.delay_values[k_nonsub[t][j]]
                notices.append(Notice(j, t, delivered, "non_substantive", None, j in suppressed, delivered > T))

    return Trajectory(cond.name, replicate, tuple(components), tuple(states), tuple(notices), tuple(joint_days))


def constant_trajectory(components: Sequence[str], T: int, states: Optional[Sequence[Sequence[int]]] = None,
                        notices: Sequence[Notice] = (), name: str = "manual") -> Trajectory:
    """A hand-built trajectory for checks and worked examples (no randomness)."""
    m = len(components)
    if states is None:
        states = [[1] * m for _ in range(T + 1)]
    if len(states) != T + 1:
        raise ValueError("states must have T + 1 rows (day 0 included)")
    return Trajectory(name, 0, tuple(components), tuple(tuple(int(v) for v in row) for row in states), tuple(notices), ())
