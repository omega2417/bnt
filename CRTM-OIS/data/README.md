# Data S1 — input data of the experiments

| File | Content |
|---|---|
| `metric_catalog.csv` | the 39 metrics of scenario BNK_PAY: goal, task, basic action, metric code and name, unit, polarity σ, class table ξ₀…ξ₅, weight, core flag, discrete step, measurement source (shared sources feed several actions) |
| `inputs_E1_E5_table_A1.csv` | input values of states E1–E5 exactly as published in Table A1 of the manuscript (`n.r.` = not reported). Used by default. |
| `inputs_E1_E5_rule12.csv` | the same states regenerated from E1 by rule (12) |
| `state_parameters.json` | state parameters t, rule, configuration version, seed, cap threshold ϑ, goal weights, and the two differences between rule (12) and Table A1 |
| `reference_values_CRTM.json` | the 15 published reference values of CRTM for state E1 (Table 5) and the enclosure of CN.S2.A1 |

Origin. Class tables, weights, core set and the values of E1 are the illustrative example of CRTM
(Korchenko et al., *Information* 2026, 17, 1170; reference implementation doi:10.5281/zenodo.23726825).
They are **not field measurements** of an operating bank. States E2–E5 are synthetic. The names of basic actions other
than UN.S1.A1 are short descriptive labels added in this software; the codes are those of the source model.

Results of the experiments are in `../results/results.json` and `../results/agents_neural.json`.
Regenerate this directory with `python scripts/export_data.py`. License: CC BY 4.0 (see `../LICENSE-DATA`).
