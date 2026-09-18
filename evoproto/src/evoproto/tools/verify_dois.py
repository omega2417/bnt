"""Verify every DOI in the reference list against CrossRef.

The article's reference list is kept as machine-readable JSON in
``docs/references/references.json`` so that it can be checked rather than
trusted.  Two levels of checking are available:

* ``--offline``: syntax only - every entry has a key, a citation string, and a
  DOI matching the CrossRef pattern ``10.NNNN/suffix`` (entries explicitly
  marked ``"doi": null``, such as books without one, are reported separately);
* online (default): each DOI is resolved through ``api.crossref.org`` and the
  returned title is compared with the stored one, so a transposed digit that
  resolves to a *different* paper is caught rather than passed.

Exit status is non-zero when any entry fails, which makes the tool usable as a
pre-submission gate in CI.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
CROSSREF_API = "https://api.crossref.org/works/"

__all__ = ["check_syntax", "main", "resolve"]


def load_references(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("references", [])
    if not isinstance(data, list):
        raise ValueError("references file must hold a list of entries")
    return data


def check_syntax(entry: dict[str, Any]) -> tuple[bool, str]:
    """Structural check of one reference entry."""
    key = entry.get("key")
    if not key:
        return False, "missing key"
    if not entry.get("citation"):
        return False, f"[{key}] missing citation string"
    doi = entry.get("doi")
    if doi is None:
        return True, f"[{key}] no DOI recorded (check this is correct for the item type)"
    if not DOI_PATTERN.match(str(doi)):
        return False, f"[{key}] malformed DOI: {doi!r}"
    return True, f"[{key}] DOI syntax ok"


def resolve(doi: str, timeout: float = 20.0, mailto: str | None = None) -> dict[str, Any]:
    """Resolve one DOI through the CrossRef REST API."""
    url = CROSSREF_API + urllib.parse.quote(doi, safe="")
    if mailto:
        url += "?" + urllib.parse.urlencode({"mailto": mailto})
    request = urllib.request.Request(
        url, headers={"User-Agent": "evoproto-doi-check/0.1 (reference verification)"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))
    message = payload.get("message", {})
    titles = message.get("title") or [""]
    return {
        "title": titles[0],
        "year": (message.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0],
        "type": message.get("type", ""),
        "container": (message.get("container-title") or [""])[0],
    }


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--references", default="docs/references/references.json")
    parser.add_argument("--offline", action="store_true", help="syntax check only")
    parser.add_argument("--mailto", default=None,
                        help="contact address for the CrossRef polite pool")
    parser.add_argument("--similarity", type=float, default=0.62,
                        help="minimum title similarity before a mismatch is reported")
    parser.add_argument("--delay", type=float, default=0.2, help="seconds between requests")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        references = load_references(args.references)
    except FileNotFoundError:
        print(f"reference list not found: {args.references}", file=sys.stderr)
        return 2

    failures = 0
    no_doi = 0
    checked = 0
    for entry in references:
        ok, message = check_syntax(entry)
        if not ok:
            failures += 1
            print(f"FAIL  {message}")
            continue
        doi = entry.get("doi")
        if doi is None:
            no_doi += 1
            print(f"SKIP  {message}")
            continue
        if args.offline:
            print(f"OK    {message}")
            continue
        try:
            record = resolve(str(doi), mailto=args.mailto)
        except urllib.error.HTTPError as error:
            failures += 1
            print(f"FAIL  [{entry['key']}] {doi} -> HTTP {error.code}")
            continue
        except Exception as error:  # network, TLS, timeout
            failures += 1
            print(f"FAIL  [{entry['key']}] {doi} -> {type(error).__name__}: {error}")
            continue
        checked += 1
        similarity = _title_similarity(entry.get("title", entry["citation"]), record["title"])
        if similarity < args.similarity:
            failures += 1
            print(f"FAIL  [{entry['key']}] title mismatch ({similarity:.2f}):")
            print(f"        stored:   {entry.get('title', '')[:90]}")
            print(f"        crossref: {record['title'][:90]}")
        else:
            print(f"OK    [{entry['key']}] {doi} -> {record['title'][:70]}")
        time.sleep(max(0.0, args.delay))

    total = len(references)
    print(f"\n{total} entries: {checked} resolved, {no_doi} without DOI, {failures} failures")
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
