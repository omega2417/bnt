"""Metadata sources: OpenAlex, Crossref, arXiv (public APIs, no key needed)."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable

from . import __version__
from .model import Record, clean_text, norm_doi

Fetch = Callable[[str], bytes]

DEFAULT_QUERIES = [
    "advertising large language models",
    "sponsored content conversational AI",
    "chatbot advertising user trust",
    "native advertising generative AI",
    "LLM sponsored product recommendation",
    "generative AI advertising disclosure consumers",
    "AI-generated advertising persuasion",
    "conversational agent advertising manipulation",
    "personalized advertising AI privacy autonomy",
    "generative engine optimization brand",
]

_STOPWORDS = {"a", "an", "and", "in", "of", "on", "the", "to", "for", "with"}


def make_fetch(mailto: str = "", pause: float = 1.0, retries: int = 4) -> Fetch:
    """HTTP GET with a polite pause and exponential backoff on 429/5xx."""
    agent = f"ai-ads-meta/{__version__}"
    if mailto:
        agent += f" (mailto:{mailto})"

    def fetch(url: str) -> bytes:
        delay = 2.0
        for attempt in range(retries + 1):
            req = urllib.request.Request(url, headers={"User-Agent": agent})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                time.sleep(pause)
                return data
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == retries:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == retries:
                    raise
            time.sleep(delay)
            delay *= 2
        raise RuntimeError("unreachable")

    return fetch


def _url(base: str, params: dict) -> str:
    return base + "?" + urllib.parse.urlencode(params)


# --------------------------------------------------------------------------- OpenAlex

def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = [(pos, w) for w, positions in inv.items() for pos in positions]
    return " ".join(w for _, w in sorted(words))


def parse_openalex(item: dict, query: str) -> Record:
    src = ((item.get("primary_location") or {}).get("source") or {})
    auths = item.get("authorships") or []
    countries: list[str] = []
    for a in auths:
        for c in a.get("countries") or []:
            if c not in countries:
                countries.append(c)
    kws = [k.get("display_name", "") for k in (item.get("keywords") or [])]
    kws += [t.get("display_name", "") for t in (item.get("topics") or [])]
    return Record(
        source="openalex",
        source_id=item.get("id") or "",
        doi=norm_doi(item.get("doi")),
        title=clean_text(item.get("title") or item.get("display_name")),
        abstract=clean_text(_openalex_abstract(item.get("abstract_inverted_index"))),
        year=item.get("publication_year"),
        date=item.get("publication_date") or "",
        venue=src.get("display_name") or "",
        type=item.get("type") or "",
        language=item.get("language") or "",
        authors=[(a.get("author") or {}).get("display_name", "") for a in auths],
        countries=countries,
        keywords=[k for k in kws if k],
        cited_by=item.get("cited_by_count"),
        open_access=(item.get("open_access") or {}).get("is_oa"),
        url=item.get("doi") or item.get("id") or "",
        queries=[query],
    )


def search_openalex(query: str, fetch: Fetch, from_year: int, limit: int) -> list[Record]:
    out: list[Record] = []
    cursor = "*"
    while cursor and len(out) < limit:
        data = json.loads(fetch(_url("https://api.openalex.org/works", {
            "search": query,
            "filter": f"from_publication_date:{from_year}-01-01",
            "per-page": min(200, limit - len(out)),
            "cursor": cursor,
        })))
        items = data.get("results") or []
        if not items:
            break
        out += [parse_openalex(i, query) for i in items]
        cursor = (data.get("meta") or {}).get("next_cursor")
    return out[:limit]


# --------------------------------------------------------------------------- Crossref

def parse_crossref(item: dict, query: str) -> Record:
    parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
    parts = [p for p in parts if p is not None]
    authors = [
        " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
        for a in item.get("author") or []
    ]
    doi = norm_doi(item.get("DOI"))
    return Record(
        source="crossref",
        source_id=doi,
        doi=doi,
        title=clean_text(" ".join(item.get("title") or [])),
        abstract=clean_text(item.get("abstract")),
        year=parts[0] if parts else None,
        date="-".join(f"{p:02d}" for p in parts),
        venue=clean_text(" ".join(item.get("container-title") or [])),
        type=item.get("type") or "",
        language=item.get("language") or "",
        authors=[a for a in authors if a],
        keywords=list(item.get("subject") or []),
        cited_by=item.get("is-referenced-by-count"),
        url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
        queries=[query],
    )


def search_crossref(query: str, fetch: Fetch, from_year: int, limit: int) -> list[Record]:
    out: list[Record] = []
    cursor = "*"
    while cursor and len(out) < limit:
        msg = json.loads(fetch(_url("https://api.crossref.org/works", {
            "query.bibliographic": query,
            "filter": f"from-pub-date:{from_year}",
            "rows": min(100, limit - len(out)),
            "cursor": cursor,
        }))).get("message") or {}
        items = msg.get("items") or []
        if not items:
            break
        out += [parse_crossref(i, query) for i in items]
        cursor = msg.get("next-cursor")
    return out[:limit]


# --------------------------------------------------------------------------- arXiv

_ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def parse_arxiv(xml_bytes: bytes, query: str) -> list[Record]:
    out = []
    for e in ET.fromstring(xml_bytes).findall("a:entry", _ATOM):
        text = lambda tag: clean_text(e.findtext(tag, "", _ATOM))  # noqa: E731
        published = text("a:published")
        url = text("a:id")
        if not url:
            continue
        out.append(Record(
            source="arxiv",
            source_id=url,
            doi=norm_doi(text("x:doi")),
            title=text("a:title"),
            abstract=text("a:summary"),
            year=int(published[:4]) if published[:4].isdigit() else None,
            date=published[:10],
            venue="arXiv",
            type="preprint",
            language="en",
            authors=[clean_text(a.findtext("a:name", "", _ATOM)) for a in e.findall("a:author", _ATOM)],
            keywords=[c.get("term", "") for c in e.findall("a:category", _ATOM)],
            open_access=True,
            url=url,
            queries=[query],
        ))
    return out


def search_arxiv(query: str, fetch: Fetch, from_year: int, limit: int) -> list[Record]:
    terms = [w for w in re.findall(r"[\w-]+", query) if w.lower() not in _STOPWORDS]
    search = " AND ".join(f"all:{w}" for w in terms)
    out: list[Record] = []
    start = 0
    while len(out) < limit:
        page = parse_arxiv(fetch(_url("https://export.arxiv.org/api/query", {
            "search_query": search,
            "start": start,
            "max_results": min(100, limit - len(out)),
            "sortBy": "relevance",
        })), query)
        if not page:
            break
        out += page
        start += len(page)
        time.sleep(3)  # arXiv asks for >= 3 s between calls
    return [r for r in out if r.year is None or r.year >= from_year][:limit]


SOURCES = {"openalex": search_openalex, "crossref": search_crossref, "arxiv": search_arxiv}


def collect(queries: list[str], sources: list[str], fetch: Fetch,
            from_year: int = 2018, limit: int = 100, log=sys.stderr) -> list[Record]:
    """Run every query against every source. A failing call is logged, not fatal."""
    records: list[Record] = []
    for name in sources:
        for q in queries:
            try:
                got = SOURCES[name](q, fetch, from_year, limit)
            except Exception as e:  # network / API errors must not lose earlier results
                print(f"[{name}] {q!r}: FAILED ({e})", file=log)
                continue
            print(f"[{name}] {q!r}: {len(got)} records", file=log)
            records += got
    return records
