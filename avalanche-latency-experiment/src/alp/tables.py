"""Result tables in CSV, Markdown and JTIT-style LaTeX.

The protocol numbers its tables; this module keeps those numbers so that
a table in the article can be traced to the exact function that produced
it.  Tables 14-16 are the result tables: they are emitted with real
numbers when a dataset exists, and with ``[DATA REQUIRED]`` placeholders
otherwise, never with the theoretical values of section 8.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .config import TOPOLOGY_LABELS, get_profile
from . import theory

DATA_REQUIRED = "[DATA REQUIRED]"


def _fmt(x, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return DATA_REQUIRED
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    return f"{x:.{digits}f}"


def to_markdown(df: pd.DataFrame, digits: int = 2) -> str:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda v: _fmt(v, digits))
    header = "| " + " | ".join(str(c) for c in out.columns) + " |"
    rule = "| " + " | ".join("---" for _ in out.columns) + " |"
    rows = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in out.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows])


#: Characters that change the meaning of a LaTeX source line.  ``%`` is the
#: dangerous one: unescaped, it comments out the rest of the line and the
#: table silently loses a column.
_TEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text: object) -> str:
    """Escape a value for inclusion in LaTeX source."""
    out = []
    for ch in str(text):
        out.append(_TEX_ESCAPES.get(ch, ch))
    return "".join(out)


def to_latex(df: pd.DataFrame, caption: str, label: str, digits: int = 2) -> str:
    """JTIT-style table: ``Tab. N`` caption above the tabular."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda v: _fmt(v, digits))
    cols = "l" * 1 + "r" * (len(out.columns) - 1)
    body = " \\\\\n".join(
        " & ".join(tex_escape(v) for v in row)
        for row in out.itertuples(index=False)
    )
    head = " & ".join(tex_escape(c) for c in out.columns)
    return (
        "\\begin{table}[t]\n"
        f"\\caption{{{tex_escape(caption)}}}\n"
        f"\\label{{{label}}}\n"
        "\\centering\n"
        f"\\begin{{tabular}}{{{cols}}}\n\\hline\n"
        f"{head} \\\\\n\\hline\n{body} \\\\\n\\hline\n"
        "\\end{tabular}\n\\end{table}\n"
    )


# --------------------------------------------------------------------------
# Result tables
# --------------------------------------------------------------------------

def table14_latency_quantiles(stability: pd.DataFrame) -> pd.DataFrame:
    """Protocol Table 14: measured quantiles of user-visible latency."""
    g = stability.groupby(["config", "topology", "load_tps"], as_index=False).agg(
        n_runs=("p50_ms", "size"),
        p50_ms=("p50_ms", "mean"),
        p95_ms=("p95_ms", "mean"),
        p99_ms=("p99_ms", "mean"),
        all_p99_ms=("all_p99_ms", "mean"),
        convergence_p99_ms=("convergence_p99_ms", "mean"),
        observed_block_ms=("observed_block_interval_ms", "median"),
    )
    g["topology"] = g.topology.map(TOPOLOGY_LABELS).fillna(g.topology)
    return g.sort_values(["config", "topology", "load_tps"]).reset_index(drop=True)


def table15_stability(cells: pd.DataFrame) -> pd.DataFrame:
    """Protocol Table 15: stability, goodput and resources."""
    out = cells.copy()
    out["stable"] = np.where(out.stable_all, "yes", "no")
    out["topology"] = out.topology.map(TOPOLOGY_LABELS).fillna(out.topology)
    cols = [
        "config", "topology", "load_tps", "goodput_mean_tps",
        "availability_min_pct", "queue_slope_mean", "cpu_p95_mean",
        "disk_p99_mean_ms", "n_stable", "n_runs", "stable",
    ]
    return out[cols].sort_values(["config", "topology", "load_tps"]).reset_index(drop=True)


def table16_effects(effects: pd.DataFrame, metrics=("p50_ms", "p95_ms", "p99_ms")) -> pd.DataFrame:
    """Protocol Table 16: effects against C0 with 95 % confidence intervals."""
    sel = effects[effects.metric.isin(metrics)].copy()
    sel["cell"] = sel.apply(
        lambda r: f"{r.delta_improvement_ms:.1f} [{r.ci_low:.1f}; {r.ci_high:.1f}]", axis=1
    )
    wide = sel.pivot_table(
        index=["profile", "topology", "load_tps"],
        columns="metric",
        values="cell",
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    rename = {m: f"delta_{m} (95% CI)" for m in metrics}
    wide = wide.rename(columns=rename)
    wide["topology"] = wide.topology.map(TOPOLOGY_LABELS).fillna(wide.topology)
    ordered = ["profile", "topology", "load_tps"] + [
        rename[m] for m in metrics if rename[m] in wide.columns
    ]
    return wide[ordered].sort_values(["profile", "topology", "load_tps"]).reset_index(drop=True)


def table_data_required(fields) -> pd.DataFrame:
    """Protocol section 16: the outstanding-data checklist as a table."""
    return pd.DataFrame(
        {"field": list(fields), "status": DATA_REQUIRED, "source": "campaign logs"}
    )


# --------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------

TABLE_CAPTIONS: Dict[str, str] = {
    "table05_tx_per_run": "Transactions per run and per repeat block (protocol Tab. 5)",
    "table09_nominal_block_rate": "Nominal block rate and block opportunities (protocol Tab. 9)",
    "table10_block_wait_theory": "Theoretical quantiles of the block-wait component only (protocol Tab. 10)",
    "table11_tx_per_block": "Mean transactions per block required to avoid backlog (protocol Tab. 11)",
    "table_campaign_arithmetic": "Campaign arithmetic, equations (1)-(4)",
    "table14_latency_quantiles": "Quantiles of user-visible latency T_visible (protocol Tab. 14)",
    "table15_stability": "Stability, goodput and resource use (protocol Tab. 15)",
    "table16_effects": "Paired effects against the C0 baseline with 95% CI (protocol Tab. 16)",
    "table_max_sustainable_load": "Maximum sustainable load per configuration and topology",
    "table_best_static": "Selected best static configuration C_best per topology",
    "table_precision_check": "Precision rule: strata needing additional repeats",
    "table_run_level_summary": "Run-level summary, one row per run (inferential unit)",
}


def write_table(df: pd.DataFrame, name: str, out_dir: Path, provenance: str) -> Dict[str, Path]:
    """Write one table as CSV, Markdown and LaTeX, with a provenance note."""
    out_dir = Path(out_dir)
    (out_dir / "csv").mkdir(parents=True, exist_ok=True)
    (out_dir / "markdown").mkdir(parents=True, exist_ok=True)
    (out_dir / "latex").mkdir(parents=True, exist_ok=True)

    caption = TABLE_CAPTIONS.get(name, name.replace("_", " "))
    note = (
        f"Provenance: {provenance}."
        + ("" if provenance == "MEASURED" else "  Not a measurement of the cyber range.")
    )

    csv_path = out_dir / "csv" / f"{name}.csv"
    df.to_csv(csv_path, index=False, lineterminator="\n", float_format="%.6f")

    md_path = out_dir / "markdown" / f"{name}.md"
    md_path.write_text(
        f"### {caption}\n\n_{note}_\n\n{to_markdown(df)}\n", encoding="utf-8"
    )

    tex_path = out_dir / "latex" / f"{name}.tex"
    tex_path.write_text(
        to_latex(df, f"{caption}. {note}", f"tab:{name}"), encoding="utf-8"
    )
    return {"csv": csv_path, "markdown": md_path, "latex": tex_path}


def write_theory_tables(out_dir: Path, profile_name: str, provenance: str) -> None:
    profile = get_profile(profile_name)
    write_table(theory.table_tx_per_run(window_s=profile.measure_s,
                                        repeats=profile.repeats),
                "table05_tx_per_run", out_dir, "THEORY")
    write_table(theory.table_nominal_rate(window_s=profile.measure_s),
                "table09_nominal_block_rate", out_dir, "THEORY")
    write_table(theory.table_block_wait(), "table10_block_wait_theory", out_dir, "THEORY")
    write_table(theory.table_tx_per_block(), "table11_tx_per_block", out_dir, "THEORY")
    write_table(theory.campaign_arithmetic(profile),
                "table_campaign_arithmetic", out_dir, "DERIVED")
