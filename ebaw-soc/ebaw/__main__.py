"""Command line: python -m ebaw {demo,dataset,validate,benchmark,test}."""
import argparse
import os
import sys

from . import __version__


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ebaw", description=f"ebaw {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo", help="narrated walk-through of the gateway protocol and attacks")
    b = sub.add_parser("dataset", help="build EBAW-SOC-Synth")
    b.add_argument("--out", default="data/ebaw-soc-synth-1.0.0")
    b.add_argument("--scenarios", nargs="*", default=None)
    v = sub.add_parser("validate", help="validate a dataset directory")
    v.add_argument("path")
    k = sub.add_parser("benchmark", help="benchmark tasks T1-T3 on a dataset directory")
    k.add_argument("path")
    k.add_argument("--split", default="test")
    a = ap.parse_args(argv)
    if a.cmd == "demo":
        from .demo import walkthrough
        walkthrough()
    elif a.cmd == "dataset":
        from . import dataset
        dataset.build(a.out, a.scenarios)
        return 1 if dataset.validate(a.out) else 0
    elif a.cmd == "validate":
        from . import dataset
        return 1 if dataset.validate(a.path) else 0
    elif a.cmd == "benchmark":
        import pandas as pd
        from . import benchmark as B, dataset
        pd.set_option("display.width", 200)
        D = dataset.load(a.path)
        c = B.task_calibration(D)
        print("T1 calibration:", {k: v for k, v in c.items() if k not in ("map", "_cal")})
        print("T2 thresholds:\n", B.task_thresholds(D, c["_cal"]).round(3).to_string(index=False))
        r = B.task_policies(D, a.split)
        print(f"T3 policies ({a.split}):\n", r["table"].round(2).to_string())
        print("sample-size planning:", r["planning"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
