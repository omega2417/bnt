# Example results (illustrative)

These files are **example outputs of the fast `smoke` campaign** (3 seeds,
6-UAV / 120 s missions), committed here only so reviewers can see the shape of
the generated artifacts without running anything. They are *not* the publication
numbers — regenerate the full results with:

```bash
aegis campaign --config configs/experiments/paper_v1.yaml
```

The live campaign writes the authoritative versions (plus CSV/LaTeX/PNG/PDF/SVG
forms and per-incident explanation objects) under `artifacts/`, which is
git-ignored so results always come from configs + seeds, never from committed
copies.

| File | Manuscript element |
|---|---|
| `table_2_parameters.md` | Table 2 — parameters (`d`, `N`, `Δ`, `κ`, `α`, `τ_e`, `w_m`, `π_min`, `λ₁`, `λ₂`) |
| `table_3_detection.md` | Table 3 — detection performance |
| `table_4_ablation.md` | Table 4 — ablation study |
| `table_5_containment.md` | Table 5 — containment effectiveness |
| `table_6_overhead.md` | Table 6 — overhead |
| `statistical_test_report.md` | Wilcoxon + Holm tests with effect sizes |
| `error_analysis.md` | Per-class error analysis |
| `manuscript_data_map.md` | Every `[DATA REQUIRED]` item → value → evidence file |
| `run_summary.json` | Headline summary |

On the smoke run the fused framework reaches F1 ≈ 0.82 (AUROC ≈ 0.97), clearly
above every single-modality and Random-Forest baseline; the full `paper_v1`
campaign tightens the confidence intervals with 20 seeds and 20-UAV missions.
