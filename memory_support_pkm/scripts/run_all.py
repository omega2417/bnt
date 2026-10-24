"""Generate the synthetic dataset, run the three conditions and write reports.

    python scripts/run_all.py [--n 240] [--days 28] [--seed 2026] [--boot 300]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")                  # headless: figures are only saved
from pgmem import pipeline, schema  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=240)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--skip-generate", action="store_true", help="analyse an existing dataset in --data")
    a = ap.parse_args()

    if not a.skip_generate:
        pipeline.generate_dataset(a.data, a.n, a.days, a.seed)
    problems = schema.validate(a.data)
    if problems:
        sys.exit("Dataset does not match datapackage.json:\n  " + "\n  ".join(problems))
    t = pipeline.load_dataset(a.data)
    ep, rc = pipeline.run_simulation(t, ROOT / "results", a.seed)
    out = pipeline.analyse(t, ep, rc, ROOT / "results", ROOT / "reports", a.boot)
    print(out["by_condition"].xs("estimate", axis=1, level=1).round(3).to_string())
    print(f"\nReport: {ROOT / 'reports' / 'summary.md'}")


if __name__ == "__main__":
    main()
