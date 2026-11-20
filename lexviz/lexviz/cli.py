"""Command line: lexviz validate | build | list | sync-json"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .data import DataError, load, sync_json
from .figures import FIGURES


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lexviz", description="LexViz: reproducible figures from provenance-tagged legal data")
    ap.add_argument("--version", action="version", version="lexviz " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    v = sub.add_parser("validate", help="check the dataset and the methodological rules")
    v.add_argument("dataset")

    b = sub.add_parser("build", help="build figures")
    b.add_argument("dataset")
    b.add_argument("-o", "--outdir", default="output")
    b.add_argument("-f", "--figure", action="append", help="figure name (repeatable); default: all")
    b.add_argument("--dpi", type=int, default=600)
    b.add_argument("--formats", default="png,pdf,svg", help="comma-separated: png,pdf,svg")
    b.add_argument("--no-gallery", action="store_true")

    sub.add_parser("list", help="list figure types")
    sub.add_parser("palette", help="check the palette under colour-vision-deficiency simulation")

    s = sub.add_parser("sync-json", help="write the JSON mirror of a YAML dataset (for devices without PyYAML)")
    s.add_argument("dataset")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "validate":
            d = load(a.dataset)
            print("OK: %s - %d areas, all rules of Section 2.3 satisfied" % (a.dataset, len(d["areas"])))
        elif a.cmd == "build":
            from .build import build
            figs = a.figure or None
            fmts = tuple(f.strip() for f in a.formats.split(",") if f.strip())
            print("Building %s -> %s/print" % (a.dataset, a.outdir))
            out = build(a.dataset, a.outdir, figs, dpi=a.dpi, formats=fmts, gallery=not a.no_gallery)
            print("Done: %d figures, %d files" % (len(out), sum(len(v) for v in out.values())))
        elif a.cmd == "list":
            for i, (name, m) in enumerate(FIGURES.items(), 1):
                print("%2d  %-26s %s" % (i, name, m.TITLE))
        elif a.cmd == "palette":
            from .palette import report
            ok, text = report()
            print(text)
            return 0 if ok else 3
        elif a.cmd == "sync-json":
            print("written", sync_json(a.dataset))
        else:
            ap.print_help()
            return 1
    except DataError as e:
        print("DATA ERROR: %s" % e, file=sys.stderr)
        return 2
    return 0
