"""Multi-format writers: every table -> CSV + LaTeX + Markdown; every figure ->
SVG + PDF + PNG.  Tables/figures are therefore always generated from the
machine-readable metrics, never hand-edited."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = ["write_table", "save_figure", "to_markdown"]


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(v) for v in row.tolist()) + " |")
    return "\n".join(lines) + "\n"


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def write_table(df: pd.DataFrame, base_path: Path, caption: str = "") -> dict[str, Path]:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    out = {}
    csv_p = base_path.with_suffix(".csv")
    df.to_csv(csv_p, index=False)
    out["csv"] = csv_p

    md_p = base_path.with_suffix(".md")
    text = (f"**{caption}**\n\n" if caption else "") + to_markdown(df)
    md_p.write_text(text)
    out["md"] = md_p

    tex_p = base_path.with_suffix(".tex")
    try:
        latex = df.to_latex(index=False, escape=True, caption=caption or None,
                            longtable=False)
    except Exception:
        latex = df.to_latex(index=False)
    tex_p.write_text(latex)
    out["tex"] = tex_p
    return out


def save_figure(fig, base_path: Path) -> dict[str, Path]:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    out = {}
    for ext in ("svg", "pdf", "png"):
        p = base_path.with_suffix(f".{ext}")
        fig.savefig(p, bbox_inches="tight", dpi=150)
        out[ext] = p
    return out
