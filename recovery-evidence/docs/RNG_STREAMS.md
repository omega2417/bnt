# Pseudo-random number consumption

This file is the normative description of every random draw in the experiment. The
implementation is `recovery_evidence/generator.py`; `tests/test_generator.py` rebuilds the
transition block from this description and compares it with the generator.

## Seeding

```python
seq = numpy.random.SeedSequence(20261123, spawn_key=(configuration_id, replicate_id, stream_id))
rng = numpy.random.Generator(numpy.random.PCG64(seq))
```

`configuration_id` is 0 … 12 for C0 … C12, `replicate_id` is 0 … 299 and `stream_id` is 0 … 4.
Conditions therefore use independent trajectories; policies within a condition share one.

## Blocks

`T` is the horizon (180), `m` the number of components (8; 10 in C9) and `K = 3` the number of
delay values (0, 1, 2). Every block is drawn in full, once, before any policy runs.

| Stream | Calls, in order | Shape | Meaning of element `[t, j]` |
| --- | --- | --- | --- |
| 0 transitions | `rng.random` | `(T+1, m)` | component `j` capable at `t−1`: becomes incapable if `< p_fail`; incapable: recovers if `< p_rec` |
| 1 notices | `rng.random` | `(T+1, m)` | if the state of `j` changed on day `t`: notice generated if `< p_report` |
| 2 delays | `rng.integers(0, K)` | `(T+1, m)` | index into `delay_values` for that substantive notice |
| 3 non-substantive | `rng.random`, then `rng.integers(0, K)` | `(T+1, m)` each | if the state of `j` did not change on day `t`: notice if `< p_nonsubstantive`; second block gives its delay index |
| 4 joint degradation | `rng.random` | `(T+1,)` | after ordinary transitions of day `t`: D and E set to 0 if `< p_joint` |

Rules that complete the description:

* Row 0 of every block belongs to day 0, the audited initial state, and is never used.
* Column `j` is the `j`-th component in alphabetical order (A … H; in C9: A, A2, B, C, D, E, F,
  F2, G, H).
* A change of state is decided by comparing the state at the start and at the end of the
  day's generator step, after joint degradation. A component failed by both mechanisms on the
  same day yields at most one notice.
* A notice is delivered on day `t + delay`. If that day is later than `T` it stays in the
  reference log with `beyond_horizon = 1` and never reaches the operator.
* In C6, notices for A and H are generated and logged with `delivered_to_operator = 0`.
* Draws that are not needed (for example the stream-1 value of a component-day without a
  change) are discarded, never reused. This is what makes the streams independent of the
  parameters: changing `p_report`, `p_nonsubstantive`, `w`, `b` or the operator's map leaves
  the hidden states of that configuration unchanged (implementation check 26).

## Analysis

`numpy.random.default_rng(20261124).integers(0, R, size=(10000, R))` gives one matrix of
resampled replicate identifiers. The same matrix is used for every contrast and outcome of a
condition, so both policies of a replicate always stay together. Interval limits are
`numpy.percentile(bootstrap_means, [2.5, 97.5])`.

No other random number is used anywhere: policies, the test module, the evaluator and the
figures are deterministic.
