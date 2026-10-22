"""Regenerates the figures from results/*.csv (360 dpi PNG + SVG)."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib
matplotlib.use("Agg")
from metatwin_guard import plots  # noqa: E402

res, fig = ROOT / "results", ROOT / "figures"
summary = list(csv.DictReader((res / "summary.csv").open()))
ablation = list(csv.DictReader((res / "ablation_executed.csv").open()))
sens = list(csv.DictReader((res / "sensitivity_executed.csv").open()))
plots.figure_topology(fig)
plots.figure_pipeline(fig)
plots.figure_f1(summary, fig)
plots.figure_f1(ablation, fig, modes=("rules", "robust", "hybrid", "integrity_only", "rules_integrity"), name="fig_ablation_executed")
plots.figure_sensitivity(sens, "power_transition", fig)
print("figures written to", fig)
