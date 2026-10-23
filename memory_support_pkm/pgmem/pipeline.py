"""End-to-end pipeline: generate -> simulate -> analyse -> report."""
from __future__ import annotations

from pathlib import Path

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
    plots.cohort_overview(cohort, reports_dir)
    plots.condition_bars(out["by_condition"], ["TSR", "FPR", "independence", "invented_outcome_rate"], reports_dir)
    plots.condition_bars(out["by_condition"], ["F_ext", "coverage", "fabricated_per_100", "appropriate_behaviour"],
                         reports_dir, "fig2b_recall.png")
    plots.tsr_by_diagnosis(pm, cohort, reports_dir)
    plots.recall_strata(out["strata"], reports_dir)
    plots.level_distribution(ep, reports_dir)
    write_report(out, t, reports_dir / "summary.md")
    return out


def _md(df: pd.DataFrame, floatfmt: str = ".3f", index: bool = True) -> str:
    return df.to_markdown(floatfmt=floatfmt, index=index)


def write_report(out, t, path: Path) -> None:
    bc = out["by_condition"].xs("estimate", axis=1, level=1)
    lines = [
        "# Звіт: provenance-governed асистент пам'яті на синтетичних даних",
        "",
        "> Усі дані синтетичні. Результати ілюструють поведінку правил рамки, а не ефективність для реальних людей.",
        "",
        f"Учасників: {len(t['participants'])}, епізодів: {len(t['episodes'])}, "
        f"записів бази подій: {len(t['records'])}, запитань: {len(t['questions'])}.",
        "",
        "## 1. Характеристика когорти (метадані)",
        "", _md(out["cohort_table"]), "",
        "## 2. Тяжкість порушення пам'яті за MoCA", "", _md(out["severity"]), "",
        "## 3. Показники за умовами (зведені, 95% кластерний бутстреп ДІ у results/by_condition.csv)",
        "", _md(bc), "",
        "## 4. Парні різниці (запропонована рамка − базові)", "", _md(out["paired"], index=False), "",
        "## 5. Безпека та інваріанти", "", _md(out["safety"]), "",
        "* `unauthorised_contact` — контакт з довіреною особою після відкликання згоди (порушення I1).",
        "* `wrong_failure` — завдання виконано, але записано як пропущене (порушення I3).", "",
        "## 6. Метадані та результат (рамка)", "", _md(out["group_tests"], index=False), "",
        "### Логістична регресія виконання епізоду", "", _md(out["logit"], index=False), "",
        "## 7. Пригадування за стратами", "", _md(out["strata"], index=False), "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
