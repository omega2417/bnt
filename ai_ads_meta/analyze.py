"""Descriptive statistics and exports for a classified corpus."""

from __future__ import annotations

import csv
import json
import os
from collections import Counter

from .model import Record
from .taxonomy import DIMENSIONS, TAXONOMY, feature_names

CSV_FIELDS = [
    "title", "year", "venue", "type", "authors", "countries", "cited_by", "doi", "url",
    "source", "open_access", "language", "relevance", "ad_format", "user_effect", "method",
    "framing", "keywords", "queries", "abstract",
]


def _cell(v):
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return "" if v is None else v


def write_csv(records: list[Record], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_FIELDS)
        for r in records:
            w.writerow([_cell(getattr(r, k)) for k in CSV_FIELDS])


def write_features(records: list[Record], path: str) -> None:
    """Binary paper x category matrix (plus year) for structure learning, e.g. in BNT."""
    names = feature_names()
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year"] + names + ["framing_risk"])
        for r in records:
            row = [r.year or ""]
            for dim in DIMENSIONS:
                codes = getattr(r, dim)
                row += [int(cat in codes) for cat in TAXONOMY[dim]]
            w.writerow(row + [int(r.framing == "risk")])


def summarize(all_records: list[Record], records: list[Record]) -> dict:
    """`records` is the relevant subset of `all_records`."""
    def count(values) -> dict:
        return dict(Counter(values).most_common())

    cross = {
        fmt: {eff: sum(1 for r in records if fmt in r.ad_format and eff in r.user_effect)
              for eff in TAXONOMY["user_effect"]}
        for fmt in TAXONOMY["ad_format"]
    }
    effect_by_year: dict[str, dict[str, int]] = {}
    for r in records:
        if r.year:
            row = effect_by_year.setdefault(str(r.year), {})
            for eff in r.user_effect:
                row[eff] = row.get(eff, 0) + 1
    top = sorted(records, key=lambda r: (r.cited_by or 0, r.relevance), reverse=True)[:20]
    return {
        "collected": len(all_records),
        "relevant": len(records),
        "by_year": dict(sorted(count(str(r.year) for r in records if r.year).items())),
        "by_source": count(s for r in records for s in r.source.split("; ")),
        "by_type": count(r.type or "unknown" for r in records),
        "by_country": count(c for r in records for c in r.countries),
        "by_venue": dict(list(count(r.venue for r in records if r.venue).items())[:20]),
        "ad_format": count(c for r in records for c in r.ad_format),
        "user_effect": count(c for r in records for c in r.user_effect),
        "method": count(c for r in records for c in r.method),
        "framing": count(r.framing for r in records),
        "format_x_effect": cross,
        "effect_by_year": dict(sorted(effect_by_year.items())),
        "top_cited": [
            {"title": r.title, "year": r.year, "venue": r.venue, "cited_by": r.cited_by, "url": r.url}
            for r in top
        ],
    }


def _table(d: dict, head: tuple[str, str], total: int | None = None) -> str:
    lines = [f"| {head[0]} | {head[1]} |" + (" % |" if total else ""),
             "|---|---:|" + ("---:|" if total else "")]
    for k, v in d.items():
        lines.append(f"| {k} | {v} |" + (f" {100 * v / total:.1f} |" if total else ""))
    return "\n".join(lines)


def render_report(s: dict) -> str:
    n = s["relevant"]
    effects = list(TAXONOMY["user_effect"])
    cross = ["| ad format \\ user effect | " + " | ".join(effects) + " |",
             "|---|" + "---:|" * len(effects)]
    for fmt, row in s["format_x_effect"].items():
        cross.append(f"| {fmt} | " + " | ".join(str(row[e]) for e in effects) + " |")
    top = "\n".join(
        f"{i}. {t['title']} ({t['year']}, {t['venue'] or 'n/a'}) - cited by {t['cited_by'] or 0}. {t['url']}"
        for i, t in enumerate(s["top_cited"], 1)
    )
    parts = [
        "# Advertising in AI systems and its effects on users: corpus summary",
        f"Records collected (after de-duplication): **{s['collected']}**; "
        f"relevant (mention both AI and advertising): **{n}**.",
        "Codes are assigned by keyword rules over title + abstract (see `taxonomy.py`); "
        "one paper can carry several codes, so shares do not sum to 100 %.",
        "## Publications per year", _table(s["by_year"], ("year", "n")),
        "## Effects on users", _table(s["user_effect"], ("effect", "n"), n) if n else "",
        "## Advertising format", _table(s["ad_format"], ("format", "n"), n) if n else "",
        "## Research method", _table(s["method"], ("method", "n"), n) if n else "",
        "## Framing (risk vs benefit cues)", _table(s["framing"], ("framing", "n"), n) if n else "",
        "## Ad format x user effect (co-occurrence counts)", "\n".join(cross),
        "## Sources", _table(s["by_source"], ("source", "n")),
        "## Top venues", _table(s["by_venue"], ("venue", "n")),
        "## Author countries", _table(dict(list(s["by_country"].items())[:15]), ("country", "n")),
        "## Most cited", top,
    ]
    return "\n\n".join(p for p in parts if p) + "\n"


def run(all_records: list[Record], out_dir: str, min_relevance: int = 1) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    relevant = [r for r in all_records if r.relevant and r.relevance >= min_relevance]
    relevant.sort(key=lambda r: (r.relevance, r.cited_by or 0), reverse=True)
    summary = summarize(all_records, relevant)
    write_csv(relevant, os.path.join(out_dir, "relevant.csv"))
    write_features(relevant, os.path.join(out_dir, "features.csv"))
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(render_report(summary))
    return summary
