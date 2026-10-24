"""End-to-end pipeline: generate -> simulate -> analyse -> report."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from . import plots, schema, simulate, stats, synth

DEFAULTS = dict(n=240, days=28, seed=2026)


def generate_dataset(data_dir: Path, n: int = 240, days: int = 28, seed: int = 2026) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cohort = synth.generate_cohort(n, seed)
    episodes = synth.generate_episodes(cohort, days)
    records, questions, reference = synth.generate_memory_corpus(cohort, seed + 1)
    tables = dict(participants=cohort, episodes=episodes, records=records, questions=questions,
                  reference_history=reference)
    for name, df in tables.items():
        df.to_csv(data_dir / f"{name}.csv", index=False)
    schema.write_descriptor(data_dir / "datapackage.json", seed, n, days)
    return tables


def load_dataset(data_dir: Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    t = {k: pd.read_csv(data_dir / f"{k}.csv") for k in schema.RESOURCES}
    t["records"]["supersedes"] = t["records"]["supersedes"].fillna("")
    return t


def run_simulation(t: dict[str, pd.DataFrame], results_dir: Path, seed: int = 2026):
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    ep = simulate.simulate_episodes(t["participants"], t["episodes"], seed + 10)
    rc = simulate.simulate_recall(t["participants"], t["records"], t["questions"], t["reference_history"], seed + 20)
    ep.to_csv(results_dir / "episode_outcomes.csv", index=False)
    rc.to_csv(results_dir / "recall_outcomes.csv", index=False)
    return ep, rc


HEADLINE = ["TSR", "FPR", "independence", "invented_outcome_rate", "F_ext", "coverage",
            "fabricated_per_100", "overstated_per_100", "appropriate_behaviour"]


def analyse(t, ep, rc, results_dir: Path, reports_dir: Path, n_boot: int = 300) -> dict[str, pd.DataFrame]:
    results_dir, reports_dir = Path(results_dir), Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    cohort = t["participants"]
    pm = stats.participant_metrics(ep, rc)
    out = {
        "cohort_table": stats.describe_cohort(cohort),
        "severity": stats.memory_impairment_profile(cohort),
        "participant_metrics": pm,
        "by_condition": pd.concat({m: stats.cluster_bootstrap(pm, m, n_boot) for m in HEADLINE}, axis=1),
        "by_condition_diagnosis": stats.pooled(pm.merge(cohort[["participant_id", "diagnosis"]]),
                                               ["diagnosis", "condition"]),
        "paired": stats.paired_differences(pm, ["TSR", "FPR", "independence", "appropriate_behaviour"]),
        "group_tests": stats.group_tests(pm, cohort),
        "logit": stats.logistic_completion(ep, cohort),
        "strata": stats.recall_by_stratum(rc),
        "safety": ep.groupby("condition")[["unauthorised_contact", "contact_cancelled", "wrong_failure",
                                           "missed_prompts"]].sum(),
    }
    for k, df in out.items():
        df.to_csv(results_dir / f"{k}.csv", index=k in ("cohort_table", "severity", "by_condition", "safety"))
    out["risk_coverage"] = stats.risk_coverage(rc)
    out["calibration"] = stats.calibrate_threshold(rc)
    out["risk_coverage"].to_csv(results_dir / "risk_coverage.csv", index=False)
    make_figures(out, t, ep, rc, reports_dir)
    write_report(out, t, reports_dir / "summary.md")
    return out


def make_figures(out, t, ep, rc, reports_dir: Path, interactive_html: bool = True) -> None:
    from . import architecture
    from .recall import THETA_HIGH, THETA_LOW
    cohort, pm = t["participants"], out["participant_metrics"]
    plots.cohort_overview(cohort, reports_dir)
    plots.condition_radar(out["by_condition"], reports_dir)
    plots.condition_dots(out["by_condition"], ["TSR", "FPR", "independence", "invented_outcome_rate"], reports_dir)
    plots.condition_dots(out["by_condition"], ["F_ext", "coverage", "fabricated_per_100", "appropriate_behaviour"],
                         reports_dir, "fig2c_dots_recall.png")
    plots.paired_forest(out["paired"], reports_dir)
    plots.tsr_raincloud(pm, cohort, reports_dir)
    plots.recall_heatmap(out["strata"], reports_dir)
    plots.invariant_scoreboard(ep, rc, reports_dir)
    plots.risk_coverage(out["risk_coverage"], THETA_LOW, THETA_HIGH, reports_dir, out["calibration"])
    plots.level_distribution(ep, reports_dir)
    plots.adaptation_over_time(ep, reports_dir)
    architecture.system_architecture(reports_dir)
    architecture.neural_recall_pipeline(reports_dir)
    plt.close("all")
    if interactive_html:
        try:
            from . import interactive as ix
        except ImportError:      # plotly is optional for the static report
            return
        html = Path(reports_dir) / "interactive"
        html.mkdir(exist_ok=True)
        ix.episode_sankey(ep, html)
        ix.recall_sunburst(rc, html)
        ix.condition_radar(out["by_condition"], html)
        ix.cohort_parallel(cohort, pm, html)
        ix.weekly_trajectories(ep, cohort, html)
        ix.risk_coverage(out["risk_coverage"], THETA_LOW, html)


def _md(df: pd.DataFrame, floatfmt: str = ".3f", index: bool = True) -> str:
    return df.to_markdown(floatfmt=floatfmt, index=index)


FIGURES = ["arch_system.png", "arch_recall_pipeline.png", "fig1_cohort.png", "fig2_radar.png", "fig2b_dots.png",
           "fig2c_dots_recall.png", "fig3_forest.png", "fig4_raincloud.png", "fig5_recall_heatmap.png",
           "fig6_invariants.png", "fig7_risk_coverage.png", "fig8_levels.png", "fig9_adaptation.png"]


def write_report(out, t, path: Path) -> None:
    bc = out["by_condition"].xs("estimate", axis=1, level=1)
    cal = out["calibration"]
    lines = [
        "# Report: provenance-governed memory assistant on synthetic data",
        "",
        "> All data are synthetic. Results illustrate how the framework rules behave, not effectiveness for real people.",
        "",
        f"Participants: {len(t['participants'])}, episodes: {len(t['episodes'])}, "
        f"event-base records: {len(t['records'])}, questions: {len(t['questions'])}.",
        "",
        "## 1. Cohort characteristics (metadata)",
        "", _md(out["cohort_table"]), "",
        "## 2. Memory-impairment severity by MoCA", "", _md(out["severity"]), "",
        "## 3. Indicators by condition (pooled; 95% cluster-bootstrap CIs in results/by_condition.csv)",
        "", _md(bc), "",
        "## 4. Paired differences (proposed framework − baselines)", "", _md(out["paired"], index=False), "",
        "## 5. Safety and invariants", "", _md(out["safety"]), "",
        "* `unauthorised_contact` — trusted-person contact after consent withdrawal (violates I1).",
        "* `wrong_failure` — task was done but recorded as missed (violates I3).", "",
        "## 6. Metadata and outcome (proposed framework)", "", _md(out["group_tests"], index=False), "",
        "### Logistic regression of episode completion", "", _md(out["logit"], index=False), "",
        "## 7. Recall by stratum", "", _md(out["strata"], index=False), "",
        "## 8. Release-rule calibration (Eq. 5)", "",
        f"Lowest θ_low reaching F_ext ≥ 0.99 on development participants: **{cal['theta_low']:.2f}**; "
        f"held-out coverage {cal['test']['coverage']:.3f}, held-out F_ext {cal['test']['F_ext']:.3f} "
        f"(default θ_low = 0.40). Full curve: results/risk_coverage.csv.", "",
        "## 9. Figures", "",
        *[f"* ![{n}]({n}) " for n in FIGURES],
        "* Interactive (open in a browser): `interactive/*.html` — Sankey of episode flow, recall sunburst, "
        "radar, parallel coordinates, weekly animation, risk–coverage.", "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
