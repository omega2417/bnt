"""Shared helpers: configuration, input/output, logging and table writing."""
from __future__ import annotations

import hashlib
import logging
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

_CODE = Path(__file__).resolve().parents[1]
CFG = SimpleNamespace(**{k: v for k, v in runpy.run_path(str(_CODE / "00_config.py")).items()
                         if k.isupper()})

for _d in (CFG.TABLES, CFG.FIGURES, CFG.LOGS, CFG.DERIVED):
    Path(_d).mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Logger writing both to the console and to output/logs/<name>.log."""
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(Path(CFG.LOGS) / f"{name}.log", mode="w", encoding="utf-8")
    sh = logging.StreamHandler(sys.stdout)
    for h in (fh, sh):
        h.setFormatter(fmt)
        log.addHandler(h)
    return log


def rng(offset: int = 0) -> np.random.Generator:
    """Reproducible generator; each script passes its own offset."""
    return np.random.default_rng(CFG.SEED + offset)


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path, **kw) -> pd.DataFrame:
    """Read a package CSV (UTF-8, comma separator, dot decimal, 'NA' = missing)."""
    return pd.read_csv(path, encoding="utf-8", keep_default_na=True, na_values=["NA"], **kw)


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8", na_rep="NA", lineterminator="\n")


def require(path: Path, hint: str = "") -> Path:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}. {hint}".strip())
    return path


# --------------------------------------------------------------------------
# Formatting of regression output
# --------------------------------------------------------------------------
def stars(p: float) -> str:
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def fmt_coef(b: float, se: float, p: float, digits: int = 3) -> str:
    if b is None or not np.isfinite(b):
        return ""
    return f"{b:.{digits}f}{stars(p)} ({se:.{digits}f})"


def to_latex(df: pd.DataFrame, path: Path, caption: str = "") -> None:
    """Minimal booktabs export next to the CSV (no jinja2 dependency)."""
    def esc(x):
        s = "" if (x is None or (isinstance(x, float) and not np.isfinite(x))) else str(x)
        for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"),
                     ("#", r"\#"), ("$", r"\$")):
            s = s.replace(a, b)
        return s
    cols = list(df.columns)
    lines = [r"\begin{tabular}{" + "l" * len(cols) + "}", r"\toprule",
             " & ".join(esc(c) for c in cols) + r" \\", r"\midrule"]
    for _, row in df.iterrows():
        lines.append(" & ".join(esc(v) for v in row.values) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    if caption:
        lines = [f"% {caption}"] + lines
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_table(df: pd.DataFrame, name: str, caption: str = "") -> None:
    """Write output/tables/<name>.csv and .tex."""
    write_csv(df, Path(CFG.TABLES) / f"{name}.csv")
    to_latex(df, Path(CFG.TABLES) / f"{name}.tex", caption)


# --------------------------------------------------------------------------
# Loading derived data
# --------------------------------------------------------------------------
def load_panel(with_covariates: bool = False) -> pd.DataFrame:
    name = "panel_covariates.csv" if with_covariates else "panel_origin_year.csv"
    hint = "Run code/03_covariates.py first." if with_covariates else "Run code/02_harmonise.py first."
    return read_csv(require(Path(CFG.DERIVED) / name, hint))


def load_policy() -> pd.DataFrame:
    return read_csv(require(Path(CFG.POLICY) / "policy_coding.csv",
                            "Run code/02_harmonise.py (policy step) first."))


def load_crosswalk() -> pd.DataFrame:
    return read_csv(require(Path(CFG.CROSSWALKS) / "citizenship_crosswalk.csv"))
