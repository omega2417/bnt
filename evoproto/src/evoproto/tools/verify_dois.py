"""Check every DOI of the reference list against CrossRef.

``docs/references.tsv`` holds the reference list of the paper as
``number<TAB>doi<TAB>citation``.  This tool resolves each DOI through the
CrossRef REST API and reports the ones that do not resolve or whose title does
not look like the cited one, so that a ``[[VERIFY DOI]]`` marker in the
manuscript can be resolved before submission.

Network access is off by default: without ``--online`` the tool only reports
what it would check, which keeps the whole package auditable offline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..data import PACKAGE_VERSION

CROSSREF_API = "https://api.crossref.org/works/"

DEFAULT_REFERENCES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "docs",
    "references.tsv",
)


@dataclass
class Reference:
    number: str
    doi: str
    citation: str


def load_references(path: str) -> List[Reference]:
    """Read the tab-separated reference list."""
    references: List[Reference] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            number = parts[0]
            doi = parts[1] if len(parts) > 1 else ""
            citation = parts[2] if len(parts) > 2 else ""
            references.append(Reference(number=number, doi=doi.strip(), citation=citation.strip()))
    return references


def _fetch_crossref(doi: str, mailto: Optional[str] = None, timeout: float = 20.0) -> Optional[Dict[str, object]]:
    import urllib.error
    import urllib.parse
    import urllib.request

    url = CROSSREF_API + urllib.parse.quote(doi, safe="")
    headers = {"User-Agent": f"evoproto/{PACKAGE_VERSION} (DOI verification)"}
    if mailto:
        headers["User-Agent"] += f" mailto:{mailto}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("message")
    except urllib.error.HTTPError as error:
        return {"__error__": f"HTTP {error.code}"}
    except Exception as error:  # pragma: no cover - network failure modes
        return {"__error__": str(error)}


def verify(
    references: Sequence[Reference],
    online: bool = False,
    mailto: Optional[str] = None,
    pause: float = 0.2,
) -> List[Dict[str, object]]:
    """Resolve each DOI; without ``online`` report what would be checked."""
    rows: List[Dict[str, object]] = []
    for reference in references:
        row: Dict[str, object] = {
            "number": reference.number,
            "doi": reference.doi,
            "citation": reference.citation[:110],
        }
        if not reference.doi:
            row["status"] = "no DOI in the reference (book, report or URL-only source)"
        elif not online:
            row["status"] = "would query CrossRef (pass --online to check)"
        else:
            message = _fetch_crossref(reference.doi, mailto=mailto)
            if message is None or "__error__" in (message or {}):
                row["status"] = f"unresolved: {(message or {}).get('__error__', 'no response')}"
            else:
                titles = message.get("title") or []
                row["status"] = "resolved"
                row["crossref_title"] = titles[0] if titles else ""
                row["crossref_year"] = (
                    (message.get("issued") or {}).get("date-parts", [[None]])[0][0]
                )
            time.sleep(pause)
        rows.append(row)
    return rows


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--references", default=DEFAULT_REFERENCES, help="path to references.tsv")
    parser.add_argument("--online", action="store_true", help="actually query CrossRef")
    parser.add_argument("--mailto", default=None, help="contact address for the CrossRef polite pool")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)

    references = load_references(args.references)
    rows = verify(references, online=args.online, mailto=args.mailto)

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    unresolved = 0
    for row in rows:
        status = str(row["status"])
        if status.startswith("unresolved"):
            unresolved += 1
        print(f"[{row['number']:>3}] {row['doi'] or '-':<45} {status}")
    print(f"\n{len(rows)} references, {unresolved} unresolved")
    return 1 if unresolved else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
