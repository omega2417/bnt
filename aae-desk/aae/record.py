"""Журнал рішень (decision record): лише дописування, позначки часу, геш-ланцюг.

Кожен запис посилається на попередників (``refs``), тож від рішення можна
пройти назад до початкового запиту (зворотна простежуваність, елемент E3).
Геш кожного запису охоплює геш попереднього, тому будь-яка пізніша зміна
або вилучення запису виявляється під час перевірки цілісності.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Callable, Iterable

GENESIS = "0" * 64
AGENT_ROLE = "agent"


class RecordError(Exception):
    """Порушення правил ведення журналу рішень."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    blob = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class DecisionRecord:
    """Append-only журнал у файлі JSON Lines (один запис на рядок)."""

    def __init__(self, path: str, clock: Callable[[], str] = _now):
        self.path = path
        self._clock = clock
        self.entries: list[dict] = []
        self._by_id: dict[str, dict] = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        entry = json.loads(line)
                        self.entries.append(entry)
                        self._by_id[entry["id"]] = entry

    def __len__(self) -> int:
        return len(self.entries)

    def get(self, entry_id: str) -> dict:
        try:
            return self._by_id[entry_id]
        except KeyError:
            raise RecordError(f"Запису {entry_id} немає в журналі") from None

    def has(self, entry_id: str) -> bool:
        return entry_id in self._by_id

    def append(self, *, id: str, type: str, actor: dict, accountable: dict,
               refs: Iterable[str] = (), payload: dict | None = None,
               task: int | None = None) -> dict:
        """Дописати запис. Наявні записи не змінюються й не вилучаються."""
        if id in self._by_id:
            raise RecordError(f"Запис {id} уже існує: журнал лише дописується")
        if accountable.get("role") == AGENT_ROLE:
            raise RecordError("ШІ-агент не може бути підзвітною стороною (правило never A)")
        if not accountable.get("name"):
            raise RecordError("Підзвітна особа має бути названа поіменно")
        refs = list(refs)
        for ref in refs:
            if ref not in self._by_id:
                raise RecordError(f"Посилання на відсутній запис {ref}")
        entry = {
            "seq": len(self.entries) + 1,
            "id": id,
            "type": type,
            "ts": self._clock(),
            "actor": actor,
            "accountable": accountable,
            "task": task,
            "refs": refs,
            "payload": payload or {},
            "prev_hash": self.entries[-1]["hash"] if self.entries else GENESIS,
        }
        entry["hash"] = _digest(entry)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.entries.append(entry)
        self._by_id[id] = entry
        return entry

    def verify(self) -> list[str]:
        """Перевірити цілісність. Повертає перелік порушень (порожній = усе гаразд)."""
        return verify_entries(self.entries)

    def trace_back(self, entry_id: str) -> list[dict]:
        """Усі попередники запису (за посиланнями), від найновішого до найдавнішого."""
        seen: dict[str, dict] = {}
        stack = [entry_id]
        while stack:
            current = self.get(stack.pop())
            if current["id"] in seen:
                continue
            seen[current["id"]] = current
            stack.extend(current["refs"])
        return sorted(seen.values(), key=lambda e: -e["seq"])


def verify_entries(entries: list[dict]) -> list[str]:
    problems: list[str] = []
    prev = GENESIS
    known: set[str] = set()
    for pos, entry in enumerate(entries, start=1):
        label = entry.get("id", f"#{pos}")
        if entry.get("seq") != pos:
            problems.append(f"{label}: порушено нумерацію (очікувалось {pos}, є {entry.get('seq')})")
        if entry.get("prev_hash") != prev:
            problems.append(f"{label}: розірвано геш-ланцюг (запис вилучено або переставлено)")
        if _digest(entry) != entry.get("hash"):
            problems.append(f"{label}: вміст запису змінено після внесення")
        if entry.get("accountable", {}).get("role") == AGENT_ROLE:
            problems.append(f"{label}: підзвітною стороною зазначено ШІ-агента")
        for ref in entry.get("refs", []):
            if ref not in known:
                problems.append(f"{label}: посилання на невідомий або пізніший запис {ref}")
        known.add(entry.get("id"))
        prev = entry.get("hash")
    return problems
