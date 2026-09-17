#!/usr/bin/env python3
"""Build a game from scratch and inspect it -- the shortest useful example.

    python examples/minimal_game.py
"""

from __future__ import annotations

from fractions import Fraction

from bircpg import (
    Action, OUTSIDE, Task, TaskAllocationGame,
    linear_congestion, pure_nash_equilibria, verify_exact_potential, welfare_maximiser,
)

# Three agents, two tasks, one controller mode.  Exact arithmetic throughout:
# pass Fractions in and every payoff, welfare and potential comes back exact.
survey, patrol = Action(0, 0), Action(1, 0)
tasks = [
    Task(value=Fraction(9), congestion=linear_congestion(Fraction(1, 2)), name="survey"),
    Task(value=Fraction(7), congestion=linear_congestion(Fraction(1, 5)), name="patrol"),
]
# Every A_i must contain the fallback (Section 4.1); agent 2 cannot reach patrol.
action_sets = [
    [survey, patrol, OUTSIDE],
    [survey, patrol, OUTSIDE],
    [survey, OUTSIDE],
]
private_cost = {
    (0, survey): Fraction(1, 2), (0, patrol): Fraction(3, 2),
    (1, survey): Fraction(2),    (1, patrol): Fraction(1, 4),
    (2, survey): Fraction(1),
}
game = TaskAllocationGame(tasks, action_sets, private_cost, label="minimal example")

print(f"{game.n_agents} agents, {game.n_tasks} tasks, |A| = {game.profile_count}")
print(verify_exact_potential(game))

equilibria = pure_nash_equilibria(game)
optimum_profile, optimum = welfare_maximiser(game)


def name(profile):
    return "(" + ", ".join("-" if a.is_outside else tasks[a.task].name for a in profile) + ")"


print(f"\npure Nash equilibria ({len(equilibria)}):")
for profile in equilibria:
    print(f"  {name(profile):26s} W = {str(game.welfare(profile)):>8s}  "
          f"Phi = {str(game.potential(profile)):>8s}")
print(f"\nwelfare optimum: {name(optimum_profile)} with W* = {optimum}")
worst = min(game.welfare(a) for a in equilibria)
print(f"additive welfare loss at the worst equilibrium: {optimum - worst}")
print("\nThe potential and welfare functions are different objects: selecting a")
print("potential maximiser does not establish welfare optimality.")
