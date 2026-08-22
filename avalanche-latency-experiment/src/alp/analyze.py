"""Statistical plan of the protocol (sections 11 and 12).

Two rules drive the whole module.

1. *The run is the inferential unit.*  Transactions inside one run share a
   block, a consensus round and a disk queue, so they are not independent
   replicates.  Every metric is first reduced to run level; only then do
   confidence intervals get built.
2. *The design is paired.*  All configurations replay the same immutable
   workload trace inside a ``topology x load x repeat`` stratum, so the
   baseline is subtracted run by run before resampling.

The module is provenance-agnostic: it consumes the JSONL layout of
protocol section 10 whether the records were measured on the cyber range
or produced by :mod:`alp.simulate`.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .config import (
    BASELINE_CONFIG,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CI_HALFWIDTH_TRIGGER,
    CI_LEVEL,
    EQUIVALENCE_BAND,
    PRIMARY_ENDPOINT,
    QUANTILES,
    THRESHOLDS,
)
from .metrics import (
    availability,
    consistency,
    empirical_quantile,
    goodput,
    half_split_drift_pct,
    observed_block_interval,
    quantile_improvement_pct,
    run_quantiles,
    theil_sen_slope_ci,
)

STRATUM = ["topology", "load_tps"]
PAIR_KEYS = ["topology", "load_tps", "repeat"]


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def read_run_records(path: Path) -> pd.DataFrame:
    """Read one run's transaction JSONL (plain or gzipped)."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return pd.DataFrame(rows)


def iter_run_files(root: Path) -> List[Path]:
    root = Path(root)
    tx_dir = root / "tx" if (root / "tx").is_dir() else root
    files = sorted(list(tx_dir.rglob("*.jsonl.gz")) + list(tx_dir.rglob("*.jsonl")))
    if not files:
        raise FileNotFoundError(f"no transaction records under {tx_dir}")
    return files


def dataset_provenance(root: Path) -> str:
    """Provenance label of a dataset, refusing to guess when it is mixed."""
    labels = set()
    for path in iter_run_files(root)[:200]:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as fh:
            first = fh.readline()
        if first.strip():
            labels.add(json.loads(first).get("provenance", "UNLABELLED"))
    if len(labels) == 1:
        return labels.pop()
    return "MIXED(" + ",".join(sorted(labels)) + ")"


# --------------------------------------------------------------------------
# Run-level reduction
# --------------------------------------------------------------------------

def summarize_run(
    records: pd.DataFrame,
    resources: Optional[pd.DataFrame] = None,
    blocks: Optional[pd.DataFrame] = None,
    window_s: Optional[float] = None,
) -> Dict[str, object]:
    """Reduce one run to the row that the statistics operate on."""
    first = records.iloc[0]
    ok = records[records.status == "success"]
    n_submitted = len(records)
    n_success = len(ok)
    n_agree = int((ok.error_class != "read_mismatch").sum()) if n_success else 0

    if window_s is None:
        span_ns = records.t_send_ns.max() - records.t_send_ns.min()
        window_s = max(span_ns / 1e9, 1e-9)

    # Bracket access throughout: several record fields ("repeat", "count")
    # collide with pandas Series methods.
    row: Dict[str, object] = {
        "run_id": first["run_id"],
        "config": first["config"],
        "topology": first["topology"],
        "load_tps": int(first["load_tps"]),
        "repeat": int(first["repeat"]),
        "trace_id": first["trace_id"],
        "provenance": first.get("provenance", "UNLABELLED"),
        "n_submitted": n_submitted,
        "n_success": n_success,
        "n_timeout": int((records.status == "timeout").sum()),
        "window_s": float(window_s),
    }
    row.update(run_quantiles(ok.t_visible_first_ms, QUANTILES))
    row.update(run_quantiles(ok.t_visible_all_ms, QUANTILES, prefix="all_"))
    row["convergence_p99_ms"] = empirical_quantile(ok.t_convergence_ms, 0.99)
    row["goodput_tps"] = goodput(n_success, window_s)
    row["availability_pct"] = availability(n_success, n_submitted)
    row["consistency_pct"] = consistency(n_agree, n_success)
    row["p99_drift_pct"] = half_split_drift_pct(
        ok.sort_values("t_send_ns").t_visible_first_ms, 0.99
    )

    if blocks is not None and len(blocks):
        row["observed_block_interval_ms"] = observed_block_interval(
            blocks.t_proposal_ms
        )
        row["tx_per_block_mean"] = float(blocks.n_tx[blocks.n_tx > 0].mean())
    else:
        row["observed_block_interval_ms"] = observed_block_interval(
            records.block_time_ms.dropna()
        )
        row["tx_per_block_mean"] = float("nan")

    if resources is not None and len(resources):
        measure = resources[resources.phase == "measure"]
        measure = measure if len(measure) >= 4 else resources
        slope = theil_sen_slope_ci(measure.queue_depth, measure.t_s, CI_LEVEL)
        row["queue_slope_tx_per_s"] = slope["slope"]
        row["queue_slope_ci_low"] = slope["ci_low"]
        row["queue_slope_ci_high"] = slope["ci_high"]
        row["queue_depth_p95"] = empirical_quantile(measure.queue_depth, 0.95)
        row["cpu_p95_pct"] = empirical_quantile(measure.cpu_pct, 0.95)
        row["cpu_max_pct"] = float(measure.cpu_pct.max())
        row["cpu_saturated_s"] = float(
            (measure.cpu_pct >= THRESHOLDS.cpu_saturation_pct).sum()
        )
        row["disk_p99_ms"] = float(measure.disk_p99_ms.max(skipna=True))
        row["mem_p95_mib"] = empirical_quantile(measure.mem_mib, 0.95)
    else:
        for key in (
            "queue_slope_tx_per_s", "queue_slope_ci_low", "queue_slope_ci_high",
            "queue_depth_p95", "cpu_p95_pct", "cpu_max_pct", "cpu_saturated_s",
            "disk_p99_ms", "mem_p95_mib",
        ):
            row[key] = float("nan")
    return row


def summarize_dataset(root: Path, progress: bool = True) -> pd.DataFrame:
    """Stream every run file and return the run-level summary table.

    Runs are processed one at a time so the full 750-run campaign never
    needs to be held in memory.
    """
    root = Path(root)
    files = iter_run_files(root)
    rows = []
    for i, path in enumerate(files, start=1):
        run_id = path.name.split(".")[0]
        records = read_run_records(path)
        res_path = root / "nodes" / f"{run_id}_resources.csv"
        blk_path = root / "nodes" / f"{run_id}_blocks.csv"
        resources = pd.read_csv(res_path) if res_path.exists() else None
        blocks = pd.read_csv(blk_path) if blk_path.exists() else None
        rows.append(summarize_run(records, resources, blocks))
        if progress and (i % 25 == 0 or i == len(files)):
            print(f"  summarised {i}/{len(files)} runs", flush=True)
    summary = pd.DataFrame(rows)
    return summary.sort_values(["config", "topology", "load_tps", "repeat"]).reset_index(
        drop=True
    )


# --------------------------------------------------------------------------
# Paired bootstrap
# --------------------------------------------------------------------------

def paired_bootstrap_delta(
    run_summary: pd.DataFrame,
    metric: str,
    profile: str,
    baseline: str = BASELINE_CONFIG,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
    level: float = CI_LEVEL,
) -> pd.DataFrame:
    """Paired improvement of ``profile`` over ``baseline`` per stratum.

    Runs are paired inside each ``topology x load`` stratum by the repeat
    that shares a ``trace_id``.  A positive delta means the profile is
    faster than the baseline, matching equation (12).
    """
    rng = np.random.default_rng(seed)
    a = run_summary[run_summary.config == profile].set_index(PAIR_KEYS)[metric]
    b = run_summary[run_summary.config == baseline].set_index(PAIR_KEYS)[metric]
    paired = pd.concat([a.rename("profile"), b.rename("baseline")], axis=1).dropna()

    alpha = 1.0 - level
    rows = []
    for (topology, load_tps), group in paired.reset_index().groupby(STRATUM):
        d = (group.baseline - group.profile).to_numpy(dtype=float)
        n = d.size
        if n == 0:
            continue
        boot = rng.choice(d, size=(replicates, n), replace=True).mean(axis=1)
        ci_low = float(np.quantile(boot, alpha / 2))
        ci_high = float(np.quantile(boot, 1 - alpha / 2))
        mean_baseline = float(group.baseline.mean())
        # Two-sided bootstrap p-value for "no difference".
        p_value = 2.0 * min(
            float((boot <= 0).mean()), float((boot >= 0).mean())
        )
        rows.append(
            {
                "metric": metric,
                "profile": profile,
                "baseline": baseline,
                "topology": topology,
                "load_tps": load_tps,
                "n_pairs": n,
                "baseline_mean": mean_baseline,
                "profile_mean": float(group.profile.mean()),
                "delta_improvement_ms": float(d.mean()),
                "delta_improvement_pct": quantile_improvement_pct(
                    mean_baseline, float(group.profile.mean())
                ),
                "ci_low": ci_low,
                "ci_high": ci_high,
                "ci_halfwidth_rel": (
                    (ci_high - ci_low) / 2.0 / abs(mean_baseline)
                    if mean_baseline
                    else float("nan")
                ),
                "p_value": min(1.0, max(p_value, 1.0 / replicates)),
                "significant": bool(ci_low > 0 or ci_high < 0),
            }
        )
    return pd.DataFrame(rows)


def all_effects(
    run_summary: pd.DataFrame,
    metrics: Iterable[str] = ("p50_ms", "p95_ms", "p99_ms", "all_p99_ms",
                             "goodput_tps", "convergence_p99_ms"),
    baseline: str = BASELINE_CONFIG,
    **kwargs,
) -> pd.DataFrame:
    """Effects of every non-baseline profile on every requested metric."""
    profiles = [c for c in run_summary.config.unique() if c != baseline]
    frames = [
        paired_bootstrap_delta(run_summary, metric, profile, baseline, **kwargs)
        for metric in metrics
        for profile in sorted(profiles)
    ]
    effects = pd.concat([f for f in frames if len(f)], ignore_index=True)
    return effects


def holm_correction(
    effects: pd.DataFrame, family_metric: str = PRIMARY_ENDPOINT
) -> pd.DataFrame:
    """Holm-Bonferroni adjustment inside the confirmatory family.

    The confirmatory family is the primary endpoint across every profile
    and stratum.  Secondary endpoints are reported with raw effect sizes
    and intervals, as the protocol requires, and are left unadjusted.
    """
    out = effects.copy()
    out["holm_p"] = np.nan
    out["holm_reject"] = pd.NA
    family = out[out.metric == family_metric].sort_values("p_value")
    m = len(family)
    if m == 0:
        return out
    adjusted, running = [], 0.0
    for rank, p in enumerate(family.p_value.to_numpy()):
        running = max(running, (m - rank) * p)
        adjusted.append(min(1.0, running))
    out.loc[family.index, "holm_p"] = adjusted
    out.loc[family.index, "holm_reject"] = np.asarray(adjusted) < (1.0 - CI_LEVEL)
    return out


def precision_check(
    effects: pd.DataFrame, metric: str = PRIMARY_ENDPOINT
) -> pd.DataFrame:
    """Apply the "add repeats" rule of the statistical plan.

    Where the 95 % CI of the primary endpoint has a relative half-width
    above 10 %, the protocol adds repeats in blocks of five, up to 30, and
    applies the rule identically to every compared regime.
    """
    sel = effects[effects.metric == metric].copy()
    sel["needs_more_repeats"] = sel.ci_halfwidth_rel > CI_HALFWIDTH_TRIGGER
    return sel[
        STRATUM + ["profile", "n_pairs", "ci_halfwidth_rel", "needs_more_repeats"]
    ].sort_values(STRATUM + ["profile"])


# --------------------------------------------------------------------------
# Stability and configuration choice (protocol section 12)
# --------------------------------------------------------------------------

def classify_stability(run_summary: pd.DataFrame, thresholds=THRESHOLDS) -> pd.DataFrame:
    """Apply the pre-registered regime rules of Table 13 to every run."""
    df = run_summary.copy()
    df["ok_availability"] = df.availability_pct >= thresholds.min_success_rate_pct
    df["ok_consistency"] = df.consistency_pct >= thresholds.min_consistency_pct
    # Unstable when the CI confirms positive backlog accumulation.
    df["ok_queue"] = ~(df.queue_slope_ci_low > 0)
    drift_ms = df.p99_drift_pct.abs() / 100.0 * df.p99_ms
    df["p99_drift_ms"] = np.where(df.p99_drift_pct >= 0, drift_ms, -drift_ms)
    df["ok_drift"] = ~(
        (df.p99_drift_pct > thresholds.max_p99_drift_pct)
        & (df.p99_drift_ms > thresholds.min_p99_drift_ms)
    )
    df["ok_cpu"] = ~(
        (df.cpu_saturated_s >= thresholds.cpu_saturation_window_s)
        & (df.queue_slope_ci_low > 0)
    )
    checks = ["ok_availability", "ok_consistency", "ok_queue", "ok_drift", "ok_cpu"]
    df["stable"] = df[checks].fillna(False).all(axis=1)
    df["failed_criteria"] = [
        ",".join(c[3:] for c in checks if not bool(row[c]))
        for _, row in df[checks].fillna(False).iterrows()
    ]
    return df


def cell_stability(stability: pd.DataFrame) -> pd.DataFrame:
    """Aggregate run stability to the ``config x topology x load`` cell.

    A cell counts as stable when every repeat satisfies every criterion,
    which is the strict reading of the protocol; the majority variant is
    reported alongside so a reviewer can see the difference.
    """
    grouped = stability.groupby(["config", "topology", "load_tps"], as_index=False)
    out = grouped.agg(
        n_runs=("stable", "size"),
        n_stable=("stable", "sum"),
        availability_min_pct=("availability_pct", "min"),
        p99_mean_ms=("p99_ms", "mean"),
        p50_mean_ms=("p50_ms", "mean"),
        goodput_mean_tps=("goodput_tps", "mean"),
        queue_slope_mean=("queue_slope_tx_per_s", "mean"),
        cpu_p95_mean=("cpu_p95_pct", "mean"),
        disk_p99_mean_ms=("disk_p99_ms", "mean"),
    )
    out["stable_all"] = out.n_stable == out.n_runs
    out["stable_majority"] = out.n_stable > out.n_runs / 2
    return out


def max_sustainable_load(cells: pd.DataFrame, rule: str = "all") -> pd.DataFrame:
    """Largest load at which a configuration stays stable, per topology.

    The protocol pre-registers two variants: ``rule="all"`` requires every
    repeat of a cell to pass, ``rule="majority"`` requires more than half.
    Both are reported by :func:`max_sustainable_load_both`, because a
    disagreement between them is itself information: it says the cell sits
    on the boundary and the precision rule should add repeats there.
    """
    column = "stable_all" if rule == "all" else "stable_majority"
    rows = []
    for (config, topology), group in cells.groupby(["config", "topology"]):
        group = group.sort_values("load_tps")
        best = 0
        for _, r in group.iterrows():
            if bool(r[column]):
                best = int(r.load_tps)
            else:
                break  # the protocol reports the largest *contiguous* load
        rows.append(
            {
                "config": config,
                "topology": topology,
                "rule": rule,
                "max_sustainable_tps": best,
            }
        )
    return pd.DataFrame(rows).sort_values(["topology", "config"])


def max_sustainable_load_both(cells: pd.DataFrame) -> pd.DataFrame:
    """Both pre-registered variants side by side, with their disagreement."""
    strict = max_sustainable_load(cells, "all").rename(
        columns={"max_sustainable_tps": "max_tps_all_repeats"}
    ).drop(columns="rule")
    majority = max_sustainable_load(cells, "majority").rename(
        columns={"max_sustainable_tps": "max_tps_majority"}
    ).drop(columns="rule")
    out = strict.merge(majority, on=["config", "topology"])
    out["rules_agree"] = out.max_tps_all_repeats == out.max_tps_majority
    return out.sort_values(["topology", "config"]).reset_index(drop=True)


def select_best_static(
    cells: pd.DataFrame,
    stability: pd.DataFrame,
    band: float = EQUIVALENCE_BAND,
) -> pd.DataFrame:
    """Choose ``C_best`` per topology (protocol section 12).

    Candidates are the configurations that remain stable over the widest
    contiguous load region.  Among them the lowest mean p99 wins; when a
    rival lies inside the +/-5 % practical-equivalence band, the tie is
    broken by lower CPU, lower disk latency and lower ``T_visible,all``,
    in that order.
    """
    reach = max_sustainable_load(cells)
    rows = []
    for topology, group in reach.groupby("topology"):
        best_reach = group.max_sustainable_tps.max()
        candidates = group[group.max_sustainable_tps == best_reach].config.tolist()
        if best_reach == 0:
            rows.append(
                {
                    "topology": topology,
                    "c_best": "none",
                    "reason": "no configuration stayed stable at the lowest load",
                    "max_sustainable_tps": 0,
                }
            )
            continue
        pool = stability[
            (stability.topology == topology)
            & (stability.config.isin(candidates))
            & (stability.load_tps <= best_reach)
            & stability.stable
        ]
        agg = pool.groupby("config").agg(
            p99_ms=("p99_ms", "mean"),
            all_p99_ms=("all_p99_ms", "mean"),
            cpu_p95_pct=("cpu_p95_pct", "mean"),
            disk_p99_ms=("disk_p99_ms", "mean"),
        )
        leader = agg.p99_ms.idxmin()
        floor = agg.p99_ms.min()
        equivalent = agg[agg.p99_ms <= floor * (1.0 + band)]
        chosen = (
            equivalent.sort_values(["cpu_p95_pct", "disk_p99_ms", "all_p99_ms"]).index[0]
            if len(equivalent) > 1
            else leader
        )
        rows.append(
            {
                "topology": topology,
                "c_best": chosen,
                "max_sustainable_tps": int(best_reach),
                "p99_mean_ms": float(agg.loc[chosen, "p99_ms"]),
                "cpu_p95_pct": float(agg.loc[chosen, "cpu_p95_pct"]),
                "equivalent_candidates": ",".join(sorted(equivalent.index)),
                "reason": (
                    "lowest mean p99"
                    if chosen == leader
                    else f"within +/-{band:.0%} of {leader}, lower resource cost"
                ),
            }
        )
    return pd.DataFrame(rows)
