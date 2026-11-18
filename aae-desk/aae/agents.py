"""Агенти F1-F4. Працюють лише з метаданими (до «межі метаданих»).

У прототипі агенти є детермінованими програмними компонентами на правилах:
це дає відтворюваність і автономну роботу без зовнішніх сервісів. Кожен агент
має вузький інтерфейс, тож його можна замінити компонентом на мовній моделі,
не змінюючи контрольних точок і журналу рішень.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

STATUS_UK = {"current": "чинна версія", "corrected": "виправлено", "superseded": "замінено новішою версією",
             "repealed": "скасовано", "retracted": "відкликано", "unknown": "статус невідомий"}
TYPE_UK = {"law": "обов'язковий правовий акт", "standard": "добровільний стандарт або настанова",
           "recommendation": "міжурядова рекомендація", "strategy": "національна стратегія",
           "article": "рецензована наукова публікація", "report": "інституційний звіт"}
ID_PATTERNS = {
    "doi": re.compile(r"^10\.\d{4,9}/\S+$"),
    "celex": re.compile(r"^3\d{4}[LRD]\d{4}$"),
    "oecd": re.compile(r"^OECD/LEGAL/\d{4}$"),
    "rada": re.compile(r"^[\w\-]+(/\d{4})?$"),
}


def load_catalog(path: str | None = None) -> dict:
    with open(path or os.path.join(DATA_DIR, "catalog.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_candidate_statements(path: str | None = None) -> dict:
    with open(path or os.path.join(DATA_DIR, "candidate_statements.json"), encoding="utf-8") as fh:
        return json.load(fh)["by_source"]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


def identifier_key(record: dict) -> str | None:
    ident = record.get("identifier")
    return f"{ident['scheme']}:{ident['value'].lower()}" if ident else None


class DiscoveryAgent:
    """F1: перетворює інформаційну потребу на запити, усуває дублікати, групує записи."""

    def __init__(self, catalog: dict):
        self.catalog = catalog

    def search(self, terms: list[str], indexes: list[str] | None = None) -> dict:
        terms = [t.strip().lower() for t in terms if t.strip()]
        hits = []
        for record in self.catalog["records"]:
            if indexes and record["index"] not in indexes:
                continue
            haystack = " ".join([record["title"], " ".join(record["keywords"])]).lower()
            words = set(_tokens(haystack))
            matched = [t for t in terms if (t in haystack if " " in t else t in words)]
            if matched:
                hits.append((len(matched), record, matched))
        hits.sort(key=lambda h: (-h[0], h[1]["key"]))
        unique, duplicates, seen = [], [], {}
        for score, record, matched in hits:
            key = identifier_key(record) or f"key:{record['key']}"
            if key in seen:
                duplicates.append({"dropped": record["key"], "kept": seen[key], "identifier": key})
                continue
            seen[key] = record["key"]
            unique.append({"record": record, "score": score, "matched_terms": matched})
        clusters: dict[str, list[str]] = {}
        for item in unique:
            clusters.setdefault(item["record"]["type"], []).append(item["record"]["key"])
        return {"terms": terms, "indexes": sorted({r["index"] for r in self.catalog["records"]
                                                   if not indexes or r["index"] in indexes}),
                "results": unique, "duplicates": duplicates, "clusters": clusters,
                "snapshot": self.catalog.get("snapshot")}


class ProvenanceAgent:
    """F2: ідентифікатор, автентичність видавця, чинна версія, статус.

    Джерела, які не вдалося розв'язати, позначаються, а не відкидаються мовчки.
    """

    def __init__(self, catalog: dict, trusted_issuers: dict):
        self.catalog = catalog
        self.trusted = trusted_issuers
        self.by_key = {r["key"]: r for r in catalog["records"]}

    def check(self, record: dict) -> dict:
        ident = record.get("identifier")
        flags: list[str] = []
        resolved = issuer_verified = False
        if not ident:
            flags.append("немає сталого ідентифікатора: джерело не розв'язано")
        elif not ID_PATTERNS.get(ident["scheme"], re.compile(r"$^")).match(ident["value"]):
            flags.append(f"ідентифікатор не відповідає формату {ident['scheme']}")
        else:
            resolved = True
            if ident["scheme"] == "doi":
                prefix = ident["value"].split("/")[0]
                expected = self.trusted.get("doi_prefix", {}).get(prefix)
            else:
                expected = self.trusted.get(ident["scheme"])
            if expected and record["issuer"] in expected:
                issuer_verified = True
            elif expected:
                flags.append(f"видавець «{record['issuer']}» не відповідає простору ідентифікаторів")
            else:
                flags.append("видавця немає в реєстрі довірених: потрібна ручна перевірка")
        status = record.get("status") or "unknown"
        current_version = None
        if status in ("superseded", "repealed", "retracted"):
            successor = self.by_key.get(record.get("superseded_by") or "")
            if successor:
                current_version = {"key": successor["key"], "title": successor["title"],
                                   "identifier": successor.get("identifier")}
            flags.append(f"{STATUS_UK[status]}" + (f"; чинне джерело: {successor['title']}" if successor else ""))
        usable = resolved and issuer_verified and status in ("current", "corrected")
        return {"resolved": resolved, "issuer_verified": issuer_verified, "status": status,
                "status_uk": STATUS_UK.get(status, status), "current_version": current_version,
                "flags": flags, "usable": usable,
                "method": "зіставлення з локальним знімком реєстрів і реєстром довірених видавців"}


class AppraisalAgent:
    """F3: пропонує оцінки актуальності, юрисдикційної застосовності й типу доказу.

    Кожна оцінка супроводжується твердженням про невизначеність. Застосовність
    до конкретної справи лежить за межею метаданих, тому агент лише пропонує
    тригер ескалації, а рішення про нього ухвалює аналітик.
    """

    def __init__(self, currency_years: int = 5, today: date | None = None):
        self.currency_years = currency_years
        self.today = today or date.today()

    def rate(self, record: dict, provenance: dict, need: dict) -> dict:
        age = self.today.year - int(record["year"])
        status = provenance["status"]
        if status in ("superseded", "repealed", "retracted"):
            currency = "застаріле"
        elif record["type"] in ("law", "strategy", "standard", "recommendation"):
            currency = "чинне" if status in ("current", "corrected") else "невідомо"
        else:
            currency = "актуальне" if age <= self.currency_years else "потребує перевірки актуальності"
        jurisdictions = need.get("jurisdictions", [])
        source_j = record.get("jurisdiction", "INT")
        suggested = []
        if source_j in jurisdictions:
            applicability = "пряма"
        elif source_j == "INT":
            applicability = "міжнародне джерело без прив'язки до юрисдикції"
        else:
            applicability = f"за аналогією (джерело: {source_j}; потреба: {', '.join(jurisdictions) or 'не зазначено'})"
            suggested.append("cross_jurisdiction")
        notes = [f"Оцінку складено лише за метаданими; зміст документа не читався."]
        if record["type"] in ("article", "report"):
            notes.append(f"Вік джерела {age} р.; методологічну якість не оцінено.")
        if not provenance["usable"]:
            notes.append("Походження не підтверджено повністю: " + "; ".join(provenance["flags"]) + ".")
        if suggested:
            notes.append("Застосовність до іншої юрисдикції має оцінити аналітик.")
        return {"currency": currency, "applicability": applicability,
                "evidence_type": TYPE_UK.get(record["type"], record["type"]),
                "uncertainty": " ".join(notes), "suggested_triggers": suggested}


class BriefingAgent:
    """F4: пропонує твердження-кандидати та складає структуровану довідку.

    ``statements`` імітує пропозиції мовної моделі (сценарні дані прототипу).
    Кандидат не є доказом, доки аналітик не підтвердить його фрагментом
    повного тексту на контрольній точці G1.
    """

    def __init__(self, statements: dict | None = None):
        self.statements = statements or {}

    def propose(self, record: dict) -> list[dict]:
        return [dict(s) for s in self.statements.get(record["key"], [])]

    @staticmethod
    def compose(need: dict, claims: list[dict], unverified: list[dict], uncertainties: list[str]) -> dict:
        options = []
        for index, title in enumerate(need["options"], start=1):
            oid = f"opt{index}"
            options.append({
                "id": oid, "title": title,
                "supporting": [c["id"] for c in claims if c["option"] == oid and c["stance"] == "supports"],
                "dissenting": [c["id"] for c in claims if c["option"] == oid and c["stance"] == "dissents"],
            })
        return {"question": need["question"], "decision": need["decision"], "options": options,
                "context": [c["id"] for c in claims if c["option"] == "context"],
                "unverified": [c["id"] for c in unverified],
                "uncertainties": uncertainties}
