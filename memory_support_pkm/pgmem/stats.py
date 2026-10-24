"""Statistics over the cohort metadata and the simulated outcomes."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import metrics as M


def describe_cohort(cohort: pd.DataFrame) -> pd.DataFrame:
    """Table of cohort characteristics by diagnosis (mean ± SD, %)."""
    def summarise(g: pd.DataFrame) -> pd.Series:
        ms = lambda c: f"{g[c].mean():.1f} ± {g[c].std():.1f}"
        pct = lambda c: f"{100 * g[c].mean():.0f}%"
        return pd.Series({
            "N": len(g),
            "Age, years": ms("age"),
            "Women": f"{100 * (g.sex == 'F').mean():.0f}%",
            "MoCA (0–30)": ms("moca"),
            "PRMQ prospective (8–40)": ms("prmq_prospective"),
            "PRMQ retrospective (8–40)": ms("prmq_retrospective"),
            "Education, years": ms("education_years"),
            "Months since diagnosis": ms("months_since_diagnosis"),
            "Lives alone": pct("lives_alone"),
            "Has trusted person": pct("has_trusted_person"),
            "Digital literacy (1–5)": ms("digital_literacy"),
            "Sensors connected": pct("sensors_connected"),
            "Call log connected": pct("call_log_connected"),
        })
    table = cohort.groupby("diagnosis").apply(summarise, include_groups=False).T
    table["Total"] = summarise(cohort)
    return table


def memory_impairment_profile(cohort: pd.DataFrame) -> pd.DataFrame:
    """Severity bands from MoCA (common cut-offs: >=26 normal, 18–25 mild,
    10–17 moderate, <10 severe) crossed with diagnosis."""
    bands = pd.cut(cohort.moca, [-1, 9, 17, 25, 30], labels=["<10 severe", "10–17 moderate", "18–25 mild", "26–30 normal"])
    return pd.crosstab(cohort.diagnosis, bands, margins=True, margins_name="Total")


def participant_metrics(ep: pd.DataFrame, rc: pd.DataFrame) -> pd.DataFrame:
    """Per participant x condition indicators (Eq. 6–7 and Section 6 extras)."""
    e = ep.assign(l01=ep.completed_true & (ep.completion_level.fillna(9) <= 1))
    eg = e.groupby(["participant_id", "condition"]).agg(
        n_scheduled=("episode_id", "size"), n_completed=("completed_true", "sum"),
        n_prompts=("prompts", "sum"), n_false=("false_prompts", "sum"), n_l01=("l01", "sum"),
        n_missed=("missed_prompts", "sum"), n_invented=("invented_outcome", "sum"),
        n_wrong_failure=("wrong_failure", "sum"), n_unauth=("unauthorised_contact", "sum"),
    )
    r = rc.assign(
        unnecessary_abstain=rc.decision.isin(["abstain", "refuse"]) & (rc.ideal == "answer"),
        appropriate_abstain=rc.decision.isin(["abstain", "refuse"]) & rc.ideal.isin(["abstain", "refuse"]),
        should_abstain=rc.ideal.isin(["abstain", "refuse"]),
    )
    rg = r.groupby(["participant_id", "condition"]).agg(
        n_questions=("question_id", "size"), n_substantive=("substantive", "sum"),
        n_released=("claims_released", "sum"), n_supported=("claims_supported", "sum"),
        n_fabricated=("fabricated", "sum"), n_overstated=("overstated", "sum"),
        n_stale=("stale_used", "sum"), n_consent=("consent_violation", "sum"),
        n_unnec_abstain=("unnecessary_abstain", "sum"), n_appr_abstain=("appropriate_abstain", "sum"),
        n_should_abstain=("should_abstain", "sum"), n_appropriate=("appropriate", "sum"),
    )
    pm = eg.join(rg).reset_index()
    return add_rates(pm)


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    v = np.vectorize
    df["TSR"] = v(M.tsr)(df.n_completed, df.n_scheduled)
    df["FPR"] = v(M.fpr)(df.n_false, df.n_prompts)
    df["independence"] = v(M.independence_index)(df.n_l01, df.n_completed)
    df["invented_outcome_rate"] = df.n_invented / df.n_scheduled
    df["F_ext"] = v(M.f_ext)(df.n_supported, df.n_released)
    df["coverage"] = v(M.coverage)(df.n_substantive, df.n_questions)
    df["fabricated_per_100"] = v(M.per_100)(df.n_fabricated, df.n_substantive)
    df["overstated_per_100"] = v(M.per_100)(df.n_overstated, df.n_substantive)
    df["appropriate_abstention"] = v(M._ratio)(df.n_appr_abstain, df.n_should_abstain)
    df["appropriate_behaviour"] = df.n_appropriate / df.n_questions
    return df


RATE_COLS = ["TSR", "FPR", "independence", "invented_outcome_rate", "F_ext", "coverage",
             "fabricated_per_100", "overstated_per_100", "appropriate_abstention", "appropriate_behaviour"]
COUNT_COLS = ["n_scheduled", "n_completed", "n_prompts", "n_false", "n_l01", "n_missed", "n_invented",
              "n_wrong_failure", "n_unauth", "n_questions", "n_substantive", "n_released", "n_supported",
              "n_fabricated", "n_overstated", "n_stale", "n_consent", "n_unnec_abstain", "n_appr_abstain",
              "n_should_abstain", "n_appropriate"]


def pooled(pm: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Ratio-of-sums indicators for any grouping."""
    return add_rates(pm.groupby(by)[COUNT_COLS].sum()).reset_index()


def cluster_bootstrap(pm: pd.DataFrame, metric: str, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Pooled metric per condition with 95% CIs resampling participants (clusters)."""
    rng = np.random.default_rng(seed)
    pids = pm.participant_id.unique()
    idx = {p: g for p, g in pm.groupby("participant_id")}
    point = pooled(pm, ["condition"]).set_index("condition")[metric]
    boots = []
    for _ in range(n_boot):
        sample = pd.concat([idx[p] for p in rng.choice(pids, len(pids))])
        boots.append(pooled(sample, ["condition"]).set_index("condition")[metric])
    b = pd.DataFrame(boots)
    return pd.DataFrame({"estimate": point, "ci_low": b.quantile(0.025), "ci_high": b.quantile(0.975)})


def paired_differences(pm: pd.DataFrame, metrics: list[str], ref: str = "proposed",
                       n_boot: int = 2000, seed: int = 1) -> pd.DataFrame:
    """Per-participant paired differences (ref − baseline) with bootstrap CI
    and a Wilcoxon signed-rank test."""
    rng = np.random.default_rng(seed)
    wide = pm.pivot(index="participant_id", columns="condition", values=metrics)
    rows = []
    for m in metrics:
        for base in [c for c in wide[m].columns if c != ref]:
            d = (wide[m][ref] - wide[m][base]).dropna().to_numpy()
            if len(d) < 5:
                continue
            bs = [rng.choice(d, len(d)).mean() for _ in range(n_boot)]
            try:
                p = stats.wilcoxon(d).pvalue if np.any(d) else 1.0
            except ValueError:
                p = np.nan
            rows.append(dict(metric=m, comparison=f"{ref} − {base}", n=len(d), mean_diff=d.mean(),
                             ci_low=np.quantile(bs, 0.025), ci_high=np.quantile(bs, 0.975), wilcoxon_p=p))
    return pd.DataFrame(rows)


def group_tests(pm: pd.DataFrame, cohort: pd.DataFrame, condition: str = "proposed") -> pd.DataFrame:
    """Association between memory-related metadata and outcomes."""
    d = pm[pm.condition == condition].merge(cohort, on="participant_id")
    rows = []
    for metric in ["TSR", "independence", "FPR", "coverage"]:
        groups = [g[metric].dropna() for _, g in d.groupby("diagnosis")]
        h, p = stats.kruskal(*groups)
        rows.append(dict(test="Kruskal–Wallis by diagnosis", outcome=metric, statistic=h, p_value=p))
        for cov in ["moca", "prmq_prospective", "age", "digital_literacy"]:
            sub = d[[cov, metric]].dropna()
            rho, p = stats.spearmanr(sub[cov], sub[metric])
            rows.append(dict(test=f"Spearman ρ with {cov}", outcome=metric, statistic=rho, p_value=p))
        a, b = d[d.lives_alone][metric].dropna(), d[~d.lives_alone][metric].dropna()
        u, p = stats.mannwhitneyu(a, b)
        rows.append(dict(test="Mann–Whitney: lives alone vs not", outcome=metric, statistic=u, p_value=p))
    return pd.DataFrame(rows)


def logistic_completion(ep: pd.DataFrame, cohort: pd.DataFrame, condition: str = "proposed") -> pd.DataFrame:
    """Episode-level logistic regression of task completion on metadata
    (Newton–Raphson, no extra dependencies).  Odds ratios with Wald 95% CI;
    note that episodes are clustered within participants, so CIs are optimistic."""
    d = ep[ep.condition == condition].merge(cohort, on="participant_id")
    X = pd.DataFrame({
        "intercept": 1.0,
        "moca_per_point": d.moca - d.moca.mean(),
        "age_per_10y": (d.age - d.age.mean()) / 10,
        "lives_alone": d.lives_alone.astype(float),
        "sensors_connected": d.sensors_connected.astype(float),
        "digital_literacy": d.digital_literacy - d.digital_literacy.mean(),
        "safety_critical_task": d.safety_critical.astype(float),
    })
    y = d.completed_true.astype(float).to_numpy()
    Xv = X.to_numpy()
    beta = np.zeros(Xv.shape[1])
    for _ in range(50):
        mu = 1 / (1 + np.exp(-Xv @ beta))
        W = mu * (1 - mu)
        H = Xv.T @ (Xv * W[:, None])
        step = np.linalg.solve(H, Xv.T @ (y - mu))
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    z = beta / se
    return pd.DataFrame({
        "term": X.columns, "OR": np.exp(beta), "ci_low": np.exp(beta - 1.96 * se),
        "ci_high": np.exp(beta + 1.96 * se), "p_value": 2 * stats.norm.sf(np.abs(z)),
    })


def recall_by_stratum(rc: pd.DataFrame) -> pd.DataFrame:
    g = rc.groupby(["stratum", "condition"]).agg(
        n=("question_id", "size"), coverage=("substantive", "mean"),
        appropriate=("appropriate", "mean"), fabricated=("fabricated", "sum"),
        overstated=("overstated", "sum"), consent_violations=("consent_violation", "sum"),
        stale=("stale_used", "sum"), wrong_event=("wrong_event", "sum"),
        released=("claims_released", "sum"), supported=("claims_supported", "sum"),
    )
    g["F_ext"] = g.supported / g.released.replace(0, np.nan)
    return g.reset_index()


def risk_coverage(rc: pd.DataFrame, condition: str = "proposed",
                  thetas: np.ndarray | None = None) -> pd.DataFrame:
    """Selective-answering curve for the release rule (Eq. 5): sweep theta_low
    over the recorded support scores S_min and recompute coverage C and F_ext.
    Gate-level abstentions (no record, conflict, permission) stay abstentions."""
    d = rc[rc.condition == condition]
    scored = d[d.s_min.notna()]
    thetas = np.round(np.linspace(0, 1, 101), 2) if thetas is None else thetas
    rows = []
    for th in thetas:
        rel = scored[scored.s_min >= th]
        rows.append(dict(theta_low=th, released=len(rel), coverage=len(rel) / len(d),
                         F_ext=rel.cand_supported.mean() if len(rel) else np.nan))
    return pd.DataFrame(rows)


def calibrate_threshold(rc: pd.DataFrame, target_f_ext: float = 0.99, dev_share: float = 0.5,
                        seed: int = 0, condition: str = "proposed") -> dict:
    """Pick the lowest theta_low reaching the target F_ext on development
    participants, then report it on held-out participants (Section 4.4)."""
    rng = np.random.default_rng(seed)
    pids = rc.participant_id.unique()
    dev = set(rng.choice(pids, int(len(pids) * dev_share), replace=False))
    is_dev = rc.participant_id.isin(dev)
    cd, ct = risk_coverage(rc[is_dev], condition), risk_coverage(rc[~is_dev], condition)
    ok = cd[cd.F_ext >= target_f_ext]
    th = float(ok.theta_low.min()) if len(ok) else 1.0
    pick = lambda c: c.loc[(c.theta_low - th).abs().idxmin()]
    return dict(theta_low=th, dev=pick(cd).to_dict(), test=pick(ct).to_dict(), curve_dev=cd, curve_test=ct)
