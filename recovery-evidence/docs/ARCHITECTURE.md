# Architecture

```
data/conditions.json ──► conditions.py ──┐
                                         ▼
 topology.py ─────────► generator.py ──► Trajectory (hidden states, notices)
     │                                     │                    │
     │ public map                          │ operator_feed()    │ states
     ▼                                     ▼                    ▼
 policies.py ◄── Operator (z, τ, n) ◄── delivered notices    TestModule.check(j)  ← one component, current day
                     │                                           ▲
                     └──────────── selected component ───────────┘
                     │ verdicts ŷ
                     ▼
               evaluate(ŷ, y)  ◄── reference_labels(states, evaluator map)
                     │
                     ▼
        results/logs/<Cx>/*.csv(.gz) ──► analysis.py (no simulator import) ──► tables ──► figures.py, claims.py
```

## Information separation

| Party | Holds | Cannot reach |
| --- | --- | --- |
| Generator | random streams, hidden states, all notices with kind and new state | policy decisions (it runs first) |
| Policy (`policies.py`) | public map, records `z`, ages, notice flags, weight `w` | anything hidden: its functions take no trajectory argument |
| Operator (`simulation.Operator`) | `z`, `τ`, `n`; delivered `(component, occurrence day)` pairs | notice kind, new state, suppressed or late notices |
| Test module | hidden states | answers one component on the current day; every query is logged |
| Evaluator | verdicts and reference labels after the run | the operator (no return path) |
| Analysis | CSV logs | the simulator code (import boundary is tested) |

Implementation checks 17 and 18 test the separation behaviourally: the query log equals the
check log, and inverting all hidden states from day 100 onward changes no decision on days
1–99.

## Equation-to-code traceability

| Article | Code | Tests |
| --- | --- | --- |
| `g_s(x)`, Section 3.2 | `DependencyMap.readiness` | checks 09; `test_topology.py` |
| `D_j(z)`, Section 3.3 | `DependencyMap.influence` | checks 02, 10 |
| `c_j`, Section 3.3 | `DependencyMap.static_importance` (exact fractions) | checks 03, 11 |
| `u_j = 1 + a_j + w n_j` | `policies.urgency` | check 01; `test_policies.py` |
| Table 3 priorities and tie-break | `policies.priorities`, `policies.select` | checks 04–06 |
| Sequential rule for `b > 1` | `simulation.run_policy` | check 16; `test_sequential_selection_recomputes_influence_within_a_day` |
| Order of events, Section 3.5 | `simulation.run_policy`, `Operator.receive` | checks 17–19 |
| Generator, Section 4.1 | `generator.generate` | checks 20–23, 26; `test_generator.py` |
| Conditions, Table 4 | `data/conditions.json` | `test_table4_parameters`, `test_each_condition_changes_one_factor`, checks 24–25 |
| FASD, FUSD, spells, Section 4.4 | `simulation.evaluate`; independently `analysis.recompute_from_verdicts` | check 15; `test_evaluator_counts_and_spells`; `test_recomputation_agrees_with_evaluator` |
| Bootstrap, MCSE, Section 4.5 | `analysis.paired_stats` | `test_paired_stats_on_known_values` |
| Appendix A | `checks.c07`, `checks.c08`; `supplementary/worked_example.py` | checks 07–08; `test_standalone_script.py` |
