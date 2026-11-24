"""Command line: python -m ai_ads_meta {collect,analyze,run,audit}"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import analyze, audit, sources
from .model import dedupe, load_jsonl, save_jsonl
from .taxonomy import classify


def _lines(path: str | None) -> list[str] | None:
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def cmd_collect(a) -> str:
    queries = _lines(a.queries) or sources.DEFAULT_QUERIES
    names = [s.strip() for s in a.sources.split(",") if s.strip()]
    unknown = set(names) - set(sources.SOURCES)
    if unknown:
        sys.exit(f"unknown source(s): {', '.join(sorted(unknown))}")
    raw = sources.collect(queries, names, sources.make_fetch(a.mailto), a.from_year, a.max_per_query)
    records = [classify(r) for r in dedupe(raw)]
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "records.jsonl")
    save_jsonl(records, path)
    print(f"{len(raw)} raw -> {len(records)} unique records: {path}", file=sys.stderr)
    if not records:
        sys.exit("no records collected (see errors above)")
    return path


def cmd_analyze(a, path: str | None = None) -> None:
    records = [classify(r) for r in load_jsonl(path or a.input)]
    s = analyze.run(records, a.out, a.min_relevance)
    print(f"{s['relevant']} relevant of {s['collected']} records; "
          f"report: {os.path.join(a.out, 'report.md')}", file=sys.stderr)


def cmd_audit(a) -> None:
    s = audit.run(a.input, a.out, _lines(a.brands))
    json.dump(s["overall"], sys.stdout, ensure_ascii=False, indent=2)
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ai_ads_meta", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def collect_args(sp):
        sp.add_argument("--out", default="ai_ads_out", help="output directory")
        sp.add_argument("--sources", default="openalex,crossref,arxiv")
        sp.add_argument("--queries", help="text file, one search query per line")
        sp.add_argument("--from-year", type=int, default=2018)
        sp.add_argument("--max-per-query", type=int, default=100)
        sp.add_argument("--mailto", default="",
                        help="contact e-mail sent to the APIs (optional; gives faster 'polite' access)")

    def analyze_args(sp):
        sp.add_argument("--min-relevance", type=int, default=1)

    sp = sub.add_parser("collect", help="harvest and classify publication metadata")
    collect_args(sp)
    sp = sub.add_parser("analyze", help="summarise a collected records.jsonl")
    sp.add_argument("--input", "-i", default="ai_ads_out/records.jsonl")
    sp.add_argument("--out", default="ai_ads_out")
    analyze_args(sp)
    sp = sub.add_parser("run", help="collect + analyze")
    collect_args(sp)
    analyze_args(sp)
    sp = sub.add_parser("audit", help="extract ad markers from chatbot responses (JSONL)")
    sp.add_argument("--input", "-i", required=True)
    sp.add_argument("--out", default="ai_ads_out")
    sp.add_argument("--brands", help="text file, one brand name per line")

    a = p.parse_args(argv)
    if a.cmd == "collect":
        cmd_collect(a)
    elif a.cmd == "analyze":
        cmd_analyze(a)
    elif a.cmd == "run":
        cmd_analyze(a, cmd_collect(a))
    else:
        cmd_audit(a)
    return 0
