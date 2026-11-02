"""Master script: runs every step in order and records the runtime of each.

    python code/run_all.py                  # full pipeline
    python code/run_all.py --from 04        # resume from step 04
    python code/run_all.py --skip-import    # start from existing data/derived (step 02 policy + 03..)

Logs: output/logs/<step>.log and output/logs/runtime.csv
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))
from lib.common import CFG, write_csv  # noqa: E402

import pandas as pd  # noqa: E402

STEPS = [
    ("01", "01_import_mrpips.py", []),
    ("02", "02_harmonise.py", []),
    ("03", "03_covariates.py", []),
    ("04", "04_concentration.py", []),
    ("05", "05_ppml.py", []),
    ("06", "06_bootstrap.py", []),
    ("07", "07_event_studies.py", []),
    ("08", "08_its.py", []),
    ("09", "09_figures.py", []),
    ("10", "10_appendix_tables.py", []),
    ("11", "11_build_appendix.py", []),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="01")
    ap.add_argument("--skip-import", action="store_true",
                    help="use existing data/derived panels; only rebuild policy coding in step 02")
    a = ap.parse_args()
    times = []
    for num, script, args in STEPS:
        if num < a.start:
            continue
        if a.skip_import and num == "01":
            continue
        if a.skip_import and num == "02":
            args = ["--policy-only"]
        t0 = time.time()
        print(f"=== {script} {' '.join(args)}", flush=True)
        r = subprocess.run([sys.executable, str(CODE / script), *args])
        times.append({"script": script, "seconds": time.time() - t0, "returncode": r.returncode})
        write_csv(pd.DataFrame(times), Path(CFG.LOGS) / "runtime.csv")
        if r.returncode != 0:
            sys.exit(f"{script} failed (see output/logs)")
    print(f"done in {sum(t['seconds'] for t in times) / 60:.1f} minutes")


if __name__ == "__main__":
    main()
