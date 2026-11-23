# Data dictionary

All files are UTF-8 CSV with a header row and `\n` line ends; `*.gz` files are gzip members
without file name and with time stamp 0. Days run from 1 to `T`; replicates from 0 to 299.

## `results/logs/<Cx>/`

**`hidden_states.csv.gz`** — reference log, never visible to a policy.
`replicate`, `day`, then one column per component (1 capable, 0 incapable).

**`notices.csv.gz`** — reference log of every generated notice.

| Column | Meaning |
| --- | --- |
| `component` | identifier |
| `occurred_day`, `delivered_day` | day of the (possibly non-substantive) event and of delivery |
| `kind` | `substantive` (a state change) or `non_substantive`; hidden from the operator |
| `new_state` | state after the change; empty for non-substantive notices; hidden from the operator |
| `delivered_to_operator` | 0 if suppressed (C6) or delivered after day `T` |
| `beyond_horizon` | 1 if `delivered_day > T` |

**`checks.csv.gz`** — one row per check.

| Column | Meaning |
| --- | --- |
| `policy`, `day`, `slot` | `slot` is 1 … `b` within the day |
| `component`, `result` | checked component and the state returned by the test module |
| `evidence_age` | `a_j` of the component when it was selected |
| `notice_flag` | `n_j` when it was selected |
| `influence` | `D_j(z)` on the operator's map when it was selected (logged for every policy) |
| `priority` | the winning priority (integer, or exact fraction for P2) |

**`verdicts.csv.gz`** — one row per (`replicate`, `policy`, `day`, `service`): `verdict` is the
operator's readiness verdict after the day's checks, `reference` the label from hidden states
on the evaluator's map.

**`trace_summary.csv`** — the evaluator's counts per (`replicate`, `policy`): `service_days`,
`false_assured`, `false_rejected`, `correct`, `assured_days` (verdict 1), `unready_days`
(reference 0), `spells`, `censored_spells`, `max_spell`, `checks`, `FASD`, `FUSD`.

## `results/tables/`

| File | Content | Article |
| --- | --- | --- |
| `policy_summary.csv` | per condition and policy: mean and MCSE of FASD, FUSD, total; share of assurances that were false; share of unready service-days falsely assured; NA counts; spell statistics; pooled FASD | Tables 5, 8; Fig. 4 |
| `paired_results.csv` | per condition, contrast and metric: mean, 95% interval, SD, median, MCSE, shares of negative/zero/positive differences | Tables 6, 8; Figs. 3, 5 |
| `paired_differences.csv` | per condition and replicate: FASD, FUSD and total of every policy | Fig. 3 |
| `allocation.csv` | mean checks per trajectory and mean evidence age at check, per component | Table 7 |
| `recheck_delay.csv` | mean days from a failed check to the next check of the same component (exploratory) | Section 5.3 |
| `table5_primary.md` … `table8_conditions.md` | the article's tables, formatted | Tables 5–8 |
| `integrity_report.txt` | comparison of recomputed outcomes with the evaluator's summaries | Section 4.6 |
| `claims_register.csv`, `manuscript_alignment.md` | printed number, recomputed number, source file, status | all |
| `analysis.json` | everything above in one machine-readable file | — |

## Other files

`results/parameters.json` (resolved configuration of C0–C12), `results/control_checks.txt`
(27 checks), `results/figures/` (Figures 1–5 as `.pdf`, `.tif`, `.png`), `results/SHA256SUMS.txt`.
