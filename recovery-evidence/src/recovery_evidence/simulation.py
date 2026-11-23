"""Operator, guarded test module and evaluator (Sections 3.1 and 3.5).

Information separation is structural, not conventional:

* :class:`TestModule` owns the hidden states.  It answers one question only:
  the state of a named component *on the current day*.  Every query is logged.
* :class:`Operator` holds records, check times and notice flags.  It never
  receives the trajectory; it receives the public map, the day's delivered
  notices and the answers of the test module for the components it selected.
* :func:`evaluate` compares stored verdicts with reference labels after the
  run; it has no path back into the operator.

Order of events within a day (Section 3.5): notices are delivered, then the
``b`` checks are made one after another with priorities recomputed after each
check, then the verdict is computed and stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .generator import Trajectory
from .policies import priorities, select
from .topology import DependencyMap


class TestModule:
    """The only gateway to hidden states during a run."""

    __test__ = False  # not a pytest class

    def __init__(self, states: Sequence[Sequence[int]]):
        self.__states = states
        self.day = 0
        self.queries: List[Tuple[int, int]] = []  # (day, component)

    def open_day(self, day: int) -> None:
        if day != self.day + 1:
            raise RuntimeError("days must be opened in order")
        self.day = day

    def check(self, component: int) -> int:
        """Exact, immediate result of verifying ``component`` today."""
        self.queries.append((self.day, component))
        return self.__states[self.day][component]


@dataclass
class Operator:
    """The operator's knowledge: records z, check times tau and notice flags n."""

    dep_map: DependencyMap
    policy: str
    w: int
    z: List[int] = field(default_factory=list)
    tau: List[int] = field(default_factory=list)
    n: List[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        m = self.dep_map.m
        # t = 0: every component has just been verified as capable (outside the budget)
        self.z, self.tau, self.n = [1] * m, [0] * m, [0] * m

    def receive(self, delivered: Sequence[Tuple[int, int]]) -> None:
        """Notice-filtering rule: a notice about a change that occurred on or
        before the day of the component's last check does not set the flag."""
        for component, occurred in delivered:
            if occurred > self.tau[component]:
                self.n[component] = 1

    def ages(self, day: int) -> List[int]:
        return [day - t for t in self.tau]

    def choose(self, day: int, already_checked: Sequence[int]):
        pr = priorities(self.policy, self.dep_map, self.z, self.ages(day), self.n, self.w)
        j = select(pr, already_checked)
        return j, pr[j]

    def record(self, component: int, day: int, result: int) -> None:
        self.z[component], self.tau[component], self.n[component] = result, day, 0

    def verdicts(self) -> Tuple[int, ...]:
        return self.dep_map.readiness_fast(self.z)


@dataclass(frozen=True)
class CheckRecord:
    day: int
    slot: int
    component: int
    result: int
    age: int  # evidence age of the component when it was selected
    notice_flag: int
    influence: int  # D_j(z) on the operator's map at selection time (logged for every policy)
    priority: str


@dataclass
class RunLog:
    policy: str
    verdicts: List[Tuple[int, ...]]  # index t-1 -> verdict vector after the checks of day t
    checks: List[CheckRecord]
    queries: List[Tuple[int, int]]
    final_records: Tuple[int, ...]


def run_policy(
    traj: Trajectory,
    policy: str,
    operator_map: DependencyMap,
    b: int,
    w: int,
) -> RunLog:
    """Replay one policy on one exogenous trajectory."""
    if operator_map.components != traj.components:
        raise ValueError("operator map and trajectory disagree on the component list")
    feed = traj.operator_feed()  # contains no hidden state
    tests = TestModule(traj.states)
    op = Operator(operator_map, policy, w)
    budget = min(b, operator_map.m)
    verdicts: List[Tuple[int, ...]] = []
    checks: List[CheckRecord] = []
    for day in range(1, traj.T + 1):
        tests.open_day(day)
        op.receive(feed[day])
        done: List[int] = []
        for slot in range(budget):
            j, pr = op.choose(day, done)
            age, flag = day - op.tau[j], op.n[j]
            infl = operator_map.influence(op.z)[j]
            result = tests.check(j)
            op.record(j, day, result)
            done.append(j)
            checks.append(CheckRecord(day, slot + 1, j, result, age, flag, infl, str(pr)))
        verdicts.append(op.verdicts())
    return RunLog(policy, verdicts, checks, tests.queries, tuple(op.z))


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TraceSummary:
    service_days: int
    false_assured: int  # verdict 1, reference 0
    false_rejected: int  # verdict 0, reference 1
    correct: int
    assured_days: int  # verdict 1
    unready_days: int  # reference 0
    spells: int  # false-assurance spells, completed and censored
    censored_spells: int  # spells still open on day T
    max_spell: int
    checks: int

    @property
    def fasd(self) -> float:
        return 100.0 * self.false_assured / self.service_days

    @property
    def fusd(self) -> float:
        return 100.0 * self.false_rejected / self.service_days


def reference_labels(traj: Trajectory, evaluator_map: DependencyMap) -> List[Tuple[int, ...]]:
    """y_s(t) = g_s(x(t)) on the evaluator's map, t = 1..T."""
    return [evaluator_map.readiness_fast(traj.states[t]) for t in range(1, traj.T + 1)]


def evaluate(verdicts: Sequence[Sequence[int]], labels: Sequence[Sequence[int]], n_checks: int = 0) -> TraceSummary:
    """Compare stored verdicts with reference labels (Section 4.4)."""
    if len(verdicts) != len(labels):
        raise ValueError("verdicts and labels cover different horizons")
    T = len(labels)
    S = len(labels[0]) if T else 0
    fa = fu = ok = assured = unready = 0
    spells = censored = longest = 0
    for s in range(S):
        run = 0
        for t in range(T):
            yh, y = verdicts[t][s], labels[t][s]
            assured += yh
            unready += 1 - y
            if yh == 1 and y == 0:
                fa += 1
                run += 1
            else:
                if yh == 0 and y == 1:
                    fu += 1
                else:
                    ok += 1
                if run:
                    spells += 1
                    longest = max(longest, run)
                    run = 0
        if run:  # spell still open on day T: right-censored
            spells += 1
            censored += 1
            longest = max(longest, run)
    return TraceSummary(S * T, fa, fu, ok, assured, unready, spells, censored, longest, n_checks)
