"""Extract advertising markers from logged chatbot responses.

Input: JSONL, one object per line with at least `response`; optional `model`,
`prompt`, `id`, `timestamp`. Only the text you supply is analysed - nothing is
sent anywhere.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter, defaultdict
from urllib.parse import parse_qs, urlparse

DISCLOSURE = re.compile(
    r"\b(?:sponsored|sponsor(?:ed)? (?:content|result|link)|advertisement|advert|promoted|paid partnership|"
    r"affiliate (?:link|disclosure)|\[ad\]|#ad|"
    r"реклама|рекламн\w+|спонсор\w+|партнерськ\w+ (?:посилання|матеріал)|на правах реклами)",
    re.I,
)
PROMO = re.compile(
    r"\b(?:buy now|order now|shop now|limited[- ]time|special offer|discount|promo code|coupon|free trial|"
    r"sign up today|best deal|sale|% off|"
    r"купи\w*|замов\w*|знижк\w+|акці[яїю]\w*|промокод\w*|безкоштовн\w+ пробн\w+|"
    r"спеціальн\w+ пропозиці\w+|вигідн\w+)",
    re.I,
)
URL = re.compile(r"https?://[^\s)\]>\"']+", re.I)
TRACKING_PARAMS = {
    "gclid", "fbclid", "msclkid", "ref", "ref_", "aff", "aff_id", "affiliate", "affid",
    "tag", "partner", "campaign", "cid", "irclickid", "clickid",
}

FIELDS = [
    "id", "model", "timestamp", "chars", "has_ad_signal", "disclosed", "undisclosed_promo",
    "n_disclosure", "n_promo", "n_urls", "n_tracking_urls", "n_brand_mentions",
    "first_signal_pos", "domains", "tracking_params", "brands", "disclosure_terms", "promo_terms",
]


def _tracking(url: str) -> list[str]:
    try:
        keys = parse_qs(urlparse(url).query, keep_blank_values=True)
    except ValueError:
        return []
    return sorted(k for k in keys if k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)


def analyze_response(entry: dict, brands: list[str] | None = None) -> dict:
    text = entry.get("response") or ""
    disclosure = list(DISCLOSURE.finditer(text))
    promo = list(PROMO.finditer(text))
    urls = [u.rstrip(".,;") for u in URL.findall(text)]
    tracking = {u: _tracking(u) for u in urls}
    tracking = {u: p for u, p in tracking.items() if p}
    brand_hits: Counter = Counter()
    positions = [m.start() for m in disclosure + promo]
    for b in brands or []:
        ms = list(re.finditer(r"(?<!\w)" + re.escape(b) + r"(?!\w)", text, re.I))
        if ms:
            brand_hits[b] = len(ms)
            positions.append(ms[0].start())
    positions += [text.find(u) for u in tracking]
    commercial = bool(promo or tracking)
    return {
        "id": entry.get("id", ""),
        "model": entry.get("model", "unknown"),
        "timestamp": entry.get("timestamp", ""),
        "chars": len(text),
        "has_ad_signal": bool(disclosure or commercial),
        "disclosed": bool(disclosure),
        # commercial cues with no disclosure label = candidate covert advertising
        "undisclosed_promo": commercial and not disclosure,
        "n_disclosure": len(disclosure),
        "n_promo": len(promo),
        "n_urls": len(urls),
        "n_tracking_urls": len(tracking),
        "n_brand_mentions": sum(brand_hits.values()),
        # 0 = start of the answer, 1 = end; empty when there is no signal
        "first_signal_pos": round(min(positions) / len(text), 3) if positions and text else "",
        "domains": sorted({urlparse(u).netloc.lower() for u in urls}),
        "tracking_params": sorted({p for ps in tracking.values() for p in ps}),
        "brands": dict(brand_hits),
        "disclosure_terms": sorted({m.group(0).lower() for m in disclosure}),
        "promo_terms": sorted({m.group(0).lower() for m in promo}),
    }


def summarize(rows: list[dict]) -> dict:
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    def stats(rs: list[dict]) -> dict:
        n = len(rs)
        share = lambda key: round(sum(bool(r[key]) for r in rs) / n, 4) if n else 0.0  # noqa: E731
        brands: Counter = Counter()
        domains: Counter = Counter()
        for r in rs:
            brands.update(r["brands"])
            domains.update(r["domains"])
        return {
            "responses": n,
            "share_with_ad_signal": share("has_ad_signal"),
            "share_disclosed": share("disclosed"),
            "share_undisclosed_promo": share("undisclosed_promo"),
            "share_with_tracking_urls": share("n_tracking_urls"),
            "share_with_brand_mentions": share("n_brand_mentions"),
            "top_brands": dict(brands.most_common(15)),
            "top_domains": dict(domains.most_common(15)),
        }

    return {"overall": stats(rows), "by_model": {m: stats(rs) for m, rs in sorted(by_model.items())}}


def run(in_path: str, out_dir: str, brands: list[str] | None = None) -> dict:
    with open(in_path, encoding="utf-8") as f:
        rows = [analyze_response(json.loads(line), brands) for line in f if line.strip()]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "audit.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([
                "; ".join(v) if isinstance(v, list)
                else json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v
                for v in (r[k] for k in FIELDS)
            ])
    summary = summarize(rows)
    with open(os.path.join(out_dir, "audit_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary
