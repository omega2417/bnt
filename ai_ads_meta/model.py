"""Unified publication record and de-duplication."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field


@dataclass
class Record:
    source: str = ""            # openalex | crossref | arxiv (";"-joined after merge)
    source_id: str = ""
    doi: str = ""
    title: str = ""
    abstract: str = ""
    year: int | None = None
    date: str = ""
    venue: str = ""
    type: str = ""
    language: str = ""
    authors: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    cited_by: int | None = None
    open_access: bool | None = None
    url: str = ""
    queries: list[str] = field(default_factory=list)
    # filled in by taxonomy.classify()
    relevant: bool | None = None
    relevance: int = 0
    ad_format: list[str] = field(default_factory=list)
    user_effect: list[str] = field(default_factory=list)
    method: list[str] = field(default_factory=list)
    framing: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Record":
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})


def clean_text(s: str | None) -> str:
    """Strip markup (JATS/HTML tags) and collapse whitespace."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_doi(doi: str | None) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi)


def _title_key(title: str) -> str:
    return re.sub(r"[^\w]+", "", title.lower())


def _union(a: list[str], b: list[str]) -> list[str]:
    out = list(a)
    for x in b:
        if x and x not in out:
            out.append(x)
    return out


def merge(a: Record, b: Record) -> Record:
    """Merge b into a: keep the richer value of every field."""
    a.source = "; ".join(_union(a.source.split("; "), b.source.split("; ")))
    for name in ("doi", "title", "date", "venue", "type", "language", "url", "source_id"):
        if not getattr(a, name):
            setattr(a, name, getattr(b, name))
    if len(b.abstract) > len(a.abstract):
        a.abstract = b.abstract
    if a.year is None:
        a.year = b.year
    if b.cited_by is not None and (a.cited_by is None or b.cited_by > a.cited_by):
        a.cited_by = b.cited_by
    if a.open_access is None:
        a.open_access = b.open_access
    if len(b.authors) > len(a.authors):
        a.authors = b.authors
    a.countries = _union(a.countries, b.countries)
    a.keywords = _union(a.keywords, b.keywords)
    a.queries = _union(a.queries, b.queries)
    return a


def dedupe(records: list[Record]) -> list[Record]:
    """Merge records sharing a DOI or (failing that) a normalised title."""
    by_doi: dict[str, Record] = {}
    by_title: dict[str, Record] = {}
    out: list[Record] = []
    for r in records:
        tkey = _title_key(r.title)
        if not tkey:
            continue
        hit = (by_doi.get(r.doi) if r.doi else None) or by_title.get(tkey)
        if hit is None:
            out.append(r)
            hit = r
        else:
            merge(hit, r)
        if hit.doi:
            by_doi[hit.doi] = hit
        by_title[tkey] = hit
    return out


def save_jsonl(records: list[Record], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")


def load_jsonl(path: str) -> list[Record]:
    with open(path, encoding="utf-8") as f:
        return [Record.from_dict(json.loads(line)) for line in f if line.strip()]
