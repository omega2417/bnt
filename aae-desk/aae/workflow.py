"""Робочий процес моделі AAE: функції F1-F4, контрольні точки G1-G3, журнал рішень.

Стан справи ніде окремо не зберігається: він щоразу відтворюється з журналу
рішень. Тому все, що вплинуло на рішення, гарантовано є в журналі.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import date

from . import autonomy, roles
from .agents import (AppraisalAgent, BriefingAgent, DiscoveryAgent, ProvenanceAgent,
                     load_candidate_statements, load_catalog)
from .config import default_config
from .record import DecisionRecord, _digest
from .roles import AGENT, ANALYST, COORDINATOR, OFFICIAL, OVERSIGHT, authorize

BUNDLE_FORMAT = "aae-evidence-bundle/1"
CONTENT_TYPES = {"zone_set", "provenance_checked", "appraisal_rated", "claim_proposed",
                 "passage_verified", "claim_confirmed", "claim_imported"}


class WorkflowError(Exception):
    """Дію не можна виконати на цьому етапі або бракує обов'язкових даних."""


def actor(role: str, name: str) -> dict:
    if role not in roles.ROLES:
        raise WorkflowError(f"Невідома роль: {role}")
    if not (name or "").strip():
        raise WorkflowError("Потрібно зазначити ім'я особи")
    return {"role": role, "name": name.strip()}


def _require(value, message: str):
    if isinstance(value, str):
        value = value.strip()
    if not value:
        raise WorkflowError(message)
    return value


class Desk:
    """Робоче місце органу: конфігурація, каталог метаданих, справи, системний журнал."""

    def __init__(self, data_dir: str, catalog: dict | None = None, statements: dict | None = None,
                 today: date | None = None, clock=None):
        self.data_dir = data_dir
        self.today = today
        self._clock = clock
        os.makedirs(os.path.join(data_dir, "cases"), exist_ok=True)
        os.makedirs(os.path.join(data_dir, "exports"), exist_ok=True)
        self._config_path = os.path.join(data_dir, "config.json")
        if os.path.exists(self._config_path):
            with open(self._config_path, encoding="utf-8") as fh:
                self.config = json.load(fh)
        else:
            self.config = default_config()
            self._save_config()
        self.catalog = catalog or load_catalog()
        self.statements = load_candidate_statements() if statements is None else statements
        self.system = self._record(os.path.join(data_dir, "system.jsonl"))

    def _record(self, path: str) -> DecisionRecord:
        return DecisionRecord(path, self._clock) if self._clock else DecisionRecord(path)

    def _save_config(self) -> None:
        with open(self._config_path, "w", encoding="utf-8") as fh:
            json.dump(self.config, fh, ensure_ascii=False, indent=1)

    # ---- справи ---------------------------------------------------------
    def case_ids(self) -> list[int]:
        names = os.listdir(os.path.join(self.data_dir, "cases"))
        return sorted(int(n[5:9]) for n in names if n.startswith("case-") and n.endswith(".jsonl"))

    def _case_path(self, number: int) -> str:
        return os.path.join(self.data_dir, "cases", f"case-{number:04d}.jsonl")

    def case(self, number: int) -> "Case":
        if number not in self.case_ids():
            raise WorkflowError(f"Справи № {number} не існує")
        return Case(self, number)

    def cases(self) -> list["Case"]:
        return [Case(self, n) for n in self.case_ids()]

    def create_case(self, who: dict, *, question: str, decision: str, options: list[str],
                    consequence: str, uncertainty: str, jurisdictions: list[str], official: str,
                    horizon: str = "", evidence_types: list[str] | None = None,
                    triggers: list[str] | None = None, consulted: str = "") -> "Case":
        """Завдання 1 (R - аналітик): визначити інформаційну потребу та межі пошуку."""
        authorize(who["role"], 1, need="R")
        options = [o.strip() for o in options if o.strip()]
        if len(options) < 2:
            raise WorkflowError("Потрібно щонайменше два варіанти рішення")
        autonomy.effective_zone(consequence, uncertainty, triggers or [], self.config["autonomy_matrix"])
        number = (self.case_ids() or [0])[-1] + 1
        case = Case(self, number)
        case.record.append(
            id=f"N-{number}", type="need_defined", task=1, actor=who,
            accountable={"role": OFFICIAL, "name": _require(official, "Потрібно назвати підзвітну посадову особу")},
            payload={"question": _require(question, "Потрібно сформулювати питання"),
                     "decision": _require(decision, "Потрібно зазначити рішення, яке підтримується"),
                     "options": options, "consequence": consequence, "uncertainty": uncertainty,
                     "jurisdictions": jurisdictions, "horizon": horizon,
                     "evidence_types": evidence_types or [], "triggers": triggers or [],
                     "analyst": who["name"], "official": official.strip(), "consulted": consulted,
                     "agency": self.config["agency"]})
        return case

    # ---- завдання 10: зміна правил і конфігурації агентів -----------------
    def revise_config(self, proposed_by: dict, approved_by: dict, changes: dict, reason: str,
                      consulted: str = "") -> dict:
        """Пропонує аналітик (R), затверджує посадова особа (A). Агент ролі не має."""
        authorize(proposed_by["role"], 10, need="R")
        authorize(approved_by["role"], 10, need="A")
        _require(reason, "Потрібно зазначити причину зміни конфігурації")
        allowed = {"autonomy_matrix", "z1_sample_rate", "currency_years", "trusted_issuers", "agents", "agency"}
        unknown = set(changes) - allowed
        if unknown or not changes:
            raise WorkflowError(f"Недозволені або порожні зміни конфігурації: {sorted(unknown)}")
        if "autonomy_matrix" in changes:
            try:
                autonomy.validate_matrix(changes["autonomy_matrix"])
            except ValueError as exc:
                raise WorkflowError(str(exc)) from None
        if "z1_sample_rate" in changes and not 0 < float(changes["z1_sample_rate"]) <= 1:
            raise WorkflowError("Частка вибіркової перевірки має бути в межах (0; 1]")
        before = {k: self.config.get(k) for k in changes}
        version = self.config["version"] + 1
        entry = self.system.append(
            id=f"G-{version}", type="config_revised", task=10, actor=proposed_by, accountable=approved_by,
            payload={"version": version, "reason": reason, "before": before, "after": changes,
                     "consulted": consulted})
        self.config.update(changes)
        self.config["version"] = version
        self._save_config()
        return entry


class Case:
    """Одна справа підготовки доказів: журнал рішень і дії над ним."""

    def __init__(self, desk: Desk, number: int):
        self.desk = desk
        self.number = number
        self.record = desk._record(desk._case_path(number))

    # ---- відтворення стану з журналу -------------------------------------
    def state(self) -> dict:
        st = {"need": None, "scope_ok": None, "zone": None, "zone_events": [], "triggers": [],
              "queries": [], "sources": {}, "candidates": {}, "verifications": {}, "claims": {},
              "research": [], "drafts": [], "signed": None, "reviews": [], "decision": None,
              "transfer_approvals": [], "transfers": [], "audits": [], "content_seq": 0}
        for e in self.record.entries:
            t, p = e["type"], e["payload"]
            if t in CONTENT_TYPES:
                st["content_seq"] = e["seq"]
            if t == "need_defined":
                st["need"] = p
            elif t == "scope_approved":
                st["scope_ok"] = e
            elif t == "zone_set":
                st["zone"], st["triggers"] = p["zone"], p["triggers"]
                st["zone_events"].append(e)
            elif t == "query_run":
                st["queries"].append(e)
            elif t == "metadata_record":
                st["sources"][p["index"]] = {"index": p["index"], "meta": e, "record": p["record"],
                                             "prov": None, "appraisal": None}
            elif t == "provenance_checked":
                st["sources"][p["index"]]["prov"] = e
            elif t == "appraisal_rated":
                st["sources"][p["index"]]["appraisal"] = e
            elif t == "claim_proposed":
                st["candidates"][e["id"]] = e
            elif t == "passage_verified":
                st["verifications"][p["candidate"]] = e
            elif t in ("claim_confirmed", "claim_imported"):
                st["claims"][e["id"]] = {"id": e["id"], "entry": e, "reused": t == "claim_imported", **p}
            elif t == "research_requested":
                st["research"].append(e)
            elif t == "brief_drafted":
                st["drafts"].append(e)
            elif t == "brief_signed":
                st["signed"] = e
            elif t == "brief_reviewed":
                st["reviews"].append(e)
            elif t == "decision_taken":
                st["decision"] = e
            elif t == "transfer_approved":
                st["transfer_approvals"].append(e)
            elif t == "evidence_transferred":
                st["transfers"].append(e)
            elif t == "audit_review":
                st["audits"].append(e)
        st["pending"] = [k for k in st["candidates"] if k not in st["verifications"]]
        st["stage"] = self._stage(st)
        return st

    @staticmethod
    def _stage(st: dict) -> str:
        if st["audits"]:
            return "Переглянуто наглядовим форумом (G3)"
        if st["decision"]:
            return "Рішення ухвалено (G2)"
        if st["signed"]:
            return "Довідку підписано, очікує рішення"
        if st["drafts"]:
            return "Проєкт довідки складено"
        if st["candidates"] or st["claims"]:
            return "Перевірка тверджень (G1)"
        if st["sources"]:
            return "Підготовка доказів (F1-F3)"
        if st["scope_ok"]:
            return "Межі затверджено"
        return "Очікує затвердження меж"

    # ---- службове --------------------------------------------------------
    def _open(self, st: dict) -> None:
        if not st["scope_ok"]:
            raise WorkflowError("Спершу підзвітна посадова особа має затвердити межі пошуку")
        if st["decision"]:
            raise WorkflowError("Рішення вже ухвалено: докази справи більше не змінюються")

    def _official(self, who: dict, st: dict) -> None:
        if who["name"] != st["need"]["official"]:
            raise WorkflowError(
                f"Цю дію виконує лише названа підзвітна посадова особа справи: {st['need']['official']}")

    def _agent(self, function: str) -> dict:
        return {"role": AGENT, "name": self.desk.config["agents"][function]}

    def _agent_allowed(self, st: dict, function: str) -> None:
        if not autonomy.agent_may(st["zone"], function):
            raise WorkflowError(
                f"У зоні Z{st['zone']} агентам не дозволено функцію {function} "
                f"«{autonomy.FUNCTIONS[function]}»: її виконує аналітик власноруч")

    def _set_zone(self, st: dict, triggers: list[str], who: dict, accountable: dict, refs, cause: str) -> dict:
        need = st["need"]
        zone = autonomy.effective_zone(need["consequence"], need["uncertainty"], triggers,
                                       self.desk.config["autonomy_matrix"])
        base = autonomy.base_zone(need["consequence"], need["uncertainty"], self.desk.config["autonomy_matrix"])
        return self.record.append(
            id=f"Z-{self.number}.{len(st['zone_events'])}", type="zone_set", actor=who, accountable=accountable,
            refs=refs, payload={"zone": zone, "base_zone": base, "previous_zone": st["zone"],
                                "triggers": triggers, "cause": cause,
                                "config_version": self.desk.config["version"]})

    # ---- завдання 1: затвердження меж -------------------------------------
    def approve_scope(self, who: dict, note: str = "") -> dict:
        authorize(who["role"], 1, need="A")
        st = self.state()
        if st["scope_ok"]:
            raise WorkflowError("Межі вже затверджено")
        self._official(who, st)
        entry = self.record.append(id=f"N-{self.number}/ok", type="scope_approved", task=1, actor=who,
                                   accountable=who, refs=[f"N-{self.number}"], payload={"note": note})
        self._set_zone(st, list(st["need"]["triggers"]), who, who, [entry["id"]], "затвердження меж")
        return entry

    def raise_trigger(self, who: dict, trigger: str, note: str = "") -> dict:
        """Аналітик може задіяти тригер ескалації без обґрунтування."""
        if who["role"] != ANALYST:
            raise roles.NotPermitted("Тригер ескалації задіює аналітик (або агент автоматично)")
        st = self.state()
        self._open(st)
        return self._trigger(st, trigger, who, who, [], note or "задіяно аналітиком")

    def _trigger(self, st, trigger, who, accountable, refs, cause):
        if trigger not in autonomy.TRIGGERS:
            raise WorkflowError(f"Невідомий тригер: {trigger}")
        if trigger in st["triggers"]:
            return st["zone_events"][-1]
        return self._set_zone(st, st["triggers"] + [trigger], who, accountable, refs,
                              f"тригер «{autonomy.TRIGGERS[trigger]}»: {cause}")

    # ---- F1: пошук джерел (завдання 2) -----------------------------------
    def run_discovery(self, who: dict, terms: list[str], indexes: list[str] | None = None,
                      because: str | None = None) -> dict:
        authorize(who["role"], 2, need="A")
        st = self.state()
        self._open(st)
        self._agent_allowed(st, "F1")
        terms = [t for t in terms if t.strip()]
        if not terms:
            raise WorkflowError("Потрібно зазначити пошукові терміни")
        agent = self._agent("F1")
        found = DiscoveryAgent(self.desk.catalog).search(terms, indexes)
        known = {s["record"]["key"] for s in st["sources"].values()}
        new = [r for r in found["results"] if r["record"]["key"] not in known]
        qid = f"Q-{self.number}.{len(st['queries']) + 1}"
        query = self.record.append(
            id=qid, type="query_run", task=2, actor=agent, accountable=who,
            refs=[because or f"N-{self.number}/ok"],
            payload={"terms": found["terms"], "indexes": found["indexes"], "snapshot": found["snapshot"],
                     "retrieved": [r["record"]["key"] for r in found["results"]],
                     "new": [r["record"]["key"] for r in new], "duplicates": found["duplicates"],
                     "clusters": found["clusters"], "requested_by": who["name"]})
        index = len(st["sources"])
        for item in new:
            index += 1
            self.record.append(
                id=f"M-{self.number}.{index}", type="metadata_record", task=2, actor=agent, accountable=who,
                refs=[qid], payload={"index": index, "record": item["record"],
                                     "matched_terms": item["matched_terms"]})
        return query

    # ---- F2: перевірка походження (завдання 3) -----------------------------
    def run_provenance(self, who: dict) -> list[dict]:
        authorize(who["role"], 3, need="A")
        st = self.state()
        self._open(st)
        self._agent_allowed(st, "F2")
        checker = ProvenanceAgent(self.desk.catalog, self.desk.config["trusted_issuers"])
        out = []
        for i, src in sorted(st["sources"].items()):
            if src["prov"]:
                continue
            result = checker.check(src["record"])
            entry = self.record.append(
                id=f"S-{self.number}.{i}", type="provenance_checked", task=3, actor=self._agent("F2"),
                accountable=who, refs=[src["meta"]["id"]], payload={"index": i, **result})
            out.append(entry)
            if not result["resolved"]:
                st = self.state()
                self._trigger(st, "provenance_unresolved", self._agent("F2"), who, [entry["id"]],
                              f"джерело {src['meta']['id']} не розв'язано")
        return out

    def record_provenance(self, who: dict, index: int, *, resolved: bool, issuer_verified: bool,
                          status: str, note: str) -> dict:
        """Ручна перевірка походження аналітиком (обов'язкова в зоні Z4)."""
        authorize(who["role"], 3, need="A")
        st = self.state()
        self._open(st)
        src = self._source(st, index)
        if src["prov"]:
            raise WorkflowError("Походження цього джерела вже перевірено")
        usable = bool(resolved and issuer_verified and status in ("current", "corrected"))
        return self.record.append(
            id=f"S-{self.number}.{index}", type="provenance_checked", task=3, actor=who, accountable=who,
            refs=[src["meta"]["id"]],
            payload={"index": index, "resolved": bool(resolved), "issuer_verified": bool(issuer_verified),
                     "status": status, "status_uk": status, "current_version": None, "usable": usable,
                     "flags": [] if usable else ["аналітик не підтвердив придатність джерела"],
                     "method": "ручна перевірка: " + _require(note, "Потрібно описати, як перевірено походження")})

    # ---- F3: оцінювання (завдання 4) --------------------------------------
    def run_appraisal(self, who: dict) -> list[dict]:
        authorize(who["role"], 4, need="A")
        st = self.state()
        self._open(st)
        self._agent_allowed(st, "F3")
        rater = AppraisalAgent(self.desk.config["currency_years"], self.desk.today)
        out = []
        for i, src in sorted(st["sources"].items()):
            if src["appraisal"] or not src["prov"]:
                continue
            rating = rater.rate(src["record"], src["prov"]["payload"], st["need"])
            out.append(self.record.append(
                id=f"R-{self.number}.{i}", type="appraisal_rated", task=4, actor=self._agent("F3"),
                accountable=who, refs=[src["prov"]["id"]], payload={"index": i, **rating}))
        return out

    def record_appraisal(self, who: dict, index: int, *, currency: str, applicability: str,
                         evidence_type: str, uncertainty: str) -> dict:
        """Оцінювання аналітиком (обов'язкове в зонах Z3 і Z4)."""
        authorize(who["role"], 4, need="A")
        st = self.state()
        self._open(st)
        src = self._source(st, index)
        if not src["prov"]:
            raise WorkflowError("Спершу потрібно перевірити походження джерела")
        if src["appraisal"]:
            raise WorkflowError("Це джерело вже оцінено")
        return self.record.append(
            id=f"R-{self.number}.{index}", type="appraisal_rated", task=4, actor=who, accountable=who,
            refs=[src["prov"]["id"]],
            payload={"index": index, "currency": _require(currency, "Зазначте актуальність"),
                     "applicability": _require(applicability, "Зазначте застосовність"),
                     "evidence_type": _require(evidence_type, "Зазначте тип доказу"),
                     "uncertainty": _require(uncertainty, "Твердження про невизначеність є обов'язковим"),
                     "suggested_triggers": []})

    @staticmethod
    def _source(st: dict, index: int) -> dict:
        if index not in st["sources"]:
            raise WorkflowError(f"Джерела № {index} у справі немає")
        return st["sources"][index]

    # ---- твердження-кандидати ---------------------------------------------
    def _next_candidate(self, st: dict, index: int) -> str:
        count = sum(1 for e in st["candidates"].values() if e["payload"]["index"] == index)
        return f"K-{self.number}.{index}.{count + 1}"

    def propose_claims(self, who: dict) -> list[dict]:
        """Агент F4 пропонує твердження-кандидати (лише в зонах Z1 і Z2)."""
        authorize(who["role"], 6, need="A")
        st = self.state()
        self._open(st)
        self._agent_allowed(st, "F4")
        agent, out = BriefingAgent(self.desk.statements), []
        for i, src in sorted(st["sources"].items()):
            if not src["prov"] or any(e["payload"]["index"] == i for e in st["candidates"].values()):
                continue
            for n, cand in enumerate(agent.propose(src["record"]), start=1):
                out.append(self.record.append(
                    id=f"K-{self.number}.{i}.{n}", type="claim_proposed", task=6, actor=self._agent("F4"),
                    accountable=who, refs=[src["prov"]["id"]],
                    payload={"index": i, "statement": cand["statement"],
                             "location_hint": cand.get("location_hint", ""), "status": "кандидат, не перевірено"}))
        return out

    def add_claim(self, who: dict, index: int, statement: str) -> dict:
        """Аналітик формулює твердження сам; воно так само проходить G1."""
        authorize(who["role"], 5, need="A")
        st = self.state()
        self._open(st)
        src = self._source(st, index)
        if not src["prov"]:
            raise WorkflowError("Спершу потрібно перевірити походження джерела")
        return self.record.append(
            id=self._next_candidate(st, index), type="claim_proposed", task=5, actor=who, accountable=who,
            refs=[src["prov"]["id"]],
            payload={"index": index, "statement": _require(statement, "Потрібен текст твердження"),
                     "location_hint": "", "status": "кандидат, не перевірено"})

    # ---- G1: перевірка за повним текстом (завдання 5) ----------------------
    def verify_claim(self, who: dict, candidate: str, verdict: str, *, reason: str, location: str = "",
                     statement: str = "", option: str = "context", stance: str = "supports",
                     grade: str = "", uncertainty: str = "", quote: str = "") -> dict:
        """Аналітик читає фрагмент і фіксує його місце та причину свого висновку.

        verdict: accept (прийнято), modify (змінено), reject (відхилено як непідтверджене).
        Причина обов'язкова для будь-якого висновку (пропозиція P5).
        """
        authorize(who["role"], 5, need="A")
        st = self.state()
        self._open(st)
        if candidate not in st["candidates"]:
            raise WorkflowError(f"Кандидата {candidate} немає")
        if candidate in st["verifications"]:
            raise WorkflowError("Це твердження вже перевірено")
        if verdict not in ("accept", "modify", "reject"):
            raise WorkflowError("Висновок має бути accept, modify або reject")
        _require(reason, "Потрібно зазначити причину прийняття, зміни чи відхилення")
        cand = st["candidates"][candidate]
        src = st["sources"][cand["payload"]["index"]]
        suffix = candidate[2:]
        if verdict != "reject":
            _require(location, "Потрібно зазначити місце фрагмента в повному тексті (стаття, пункт, сторінка)")
            if not src["prov"]["payload"]["usable"]:
                raise WorkflowError("Джерело не пройшло перевірку походження, тому не може підтверджувати твердження")
            valid = {f"opt{i}" for i in range(1, len(st["need"]["options"]) + 1)} | {"context"}
            if option not in valid or stance not in ("supports", "dissents"):
                raise WorkflowError("Потрібно зазначити варіант рішення та характер доказу (за чи проти)")
            if verdict == "modify":
                _require(statement, "Для зміни потрібен уточнений текст твердження")
        passage = self.record.append(
            id=f"P-{suffix}", type="passage_verified", task=5, actor=who, accountable=who,
            refs=[src["prov"]["id"], candidate],
            payload={"candidate": candidate, "verdict": verdict, "reason": reason, "location": location,
                     "quote": quote, "reader": who["name"],
                     "proposed_by": cand["actor"]["role"]})
        if verdict == "reject":
            return passage
        return self.record.append(
            id=f"C-{suffix}", type="claim_confirmed", task=5, actor=who, accountable=who, refs=[passage["id"]],
            payload={"statement": statement.strip() if verdict == "modify" else cand["payload"]["statement"],
                     "index": cand["payload"]["index"], "location": location, "option": option,
                     "stance": stance, "grade": grade or src["appraisal"]["payload"]["evidence_type"]
                     if src["appraisal"] else grade, "uncertainty": uncertainty, "modified": verdict == "modify"})

    def request_research(self, who: dict, candidate: str, terms: list[str]) -> dict:
        """Петля ескалації: непідтверджене твердження повертається до пошуку (F1)."""
        authorize(who["role"], 5, need="A")
        st = self.state()
        ver = st["verifications"].get(candidate)
        if not ver or ver["payload"]["verdict"] != "reject":
            raise WorkflowError("До пошуку повертають лише твердження, відхилені на G1")
        loop = self.record.append(
            id=f"L-{self.number}.{len(st['research']) + 1}", type="research_requested", task=5, actor=who,
            accountable=who, refs=[ver["id"]], payload={"candidate": candidate, "terms": terms})
        return self.run_discovery(who, terms, because=loop["id"])

    # ---- F4: довідка (завдання 6) ----------------------------------------
    def g1_status(self, st: dict | None = None) -> dict:
        st = st or self.state()
        total, checked = len(st["candidates"]), len(st["verifications"])
        if st["zone"] == 1:
            required = max(1, math.ceil(self.desk.config["z1_sample_rate"] * total)) if total else 0
        else:
            required = total
        return {"total": total, "checked": checked, "required": required, "passed": checked >= required,
                "mode": autonomy.ZONES[st["zone"]]["g1"] if st["zone"] else None}

    def _uncertainties(self, st: dict) -> list[str]:
        notes = []
        for t in st["triggers"]:
            notes.append(f"Задіяно тригер ескалації: {autonomy.TRIGGERS[t]}.")
        for i, src in sorted(st["sources"].items()):
            if src["prov"] and not src["prov"]["payload"]["usable"]:
                flags = "; ".join(src["prov"]["payload"]["flags"])
                notes.append(f"Джерело {src['prov']['id']} «{_short(src['record']['title'])}» не використано: {flags}.")
            if not src["prov"]:
                notes.append(f"Джерело {src['meta']['id']} не перевірено на походження і не використано.")
        rejected = [v for v in st["verifications"].values() if v["payload"]["verdict"] == "reject"]
        if rejected:
            notes.append(f"На G1 відхилено як непідтверджені {len(rejected)} тверджень-кандидатів: "
                         + ", ".join(v["payload"]["candidate"] for v in rejected) + ".")
        for c in st["claims"].values():
            if c.get("uncertainty"):
                notes.append(f"{c['id']}: {c['uncertainty']}")
        if st["pending"]:
            notes.append(f"{len(st['pending'])} тверджень не перевірено за повним текстом (вибірковий аудит зони Z1).")
        return notes

    def draft_brief(self, who: dict) -> dict:
        authorize(who["role"], 6, need="A")
        st = self.state()
        self._open(st)
        g1 = self.g1_status(st)
        if not g1["passed"]:
            raise WorkflowError(
                f"Контрольну точку G1 не пройдено: перевірено {g1['checked']} з {g1['required']} обов'язкових тверджень")
        if not st["claims"]:
            raise WorkflowError("Немає жодного підтвердженого твердження для довідки")
        claims = list(st["claims"].values())
        unverified = [{"id": k} for k in st["pending"]]
        content = BriefingAgent.compose(st["need"], claims, unverified, self._uncertainties(st))
        by_agent = autonomy.agent_may(st["zone"], "F4")
        return self.record.append(
            id=f"B-{self.number}/d{len(st['drafts']) + 1}", type="brief_drafted", task=6,
            actor=self._agent("F4") if by_agent else who, accountable=who,
            refs=[c["id"] for c in claims] + st["pending"],
            payload={"content": content, "zone": st["zone"], "requested_by": who["name"]})

    def sign_brief(self, who: dict, assessment: str, recommended: str = "") -> dict:
        """Аналітик редагує й підписує довідку та стає її підзвітним автором."""
        authorize(who["role"], 6, need="A")
        st = self.state()
        self._open(st)
        if not st["drafts"] or st["drafts"][-1]["seq"] < st["content_seq"]:
            raise WorkflowError("Потрібен актуальний проєкт довідки (докази або зона змінилися після останнього)")
        draft = st["drafts"][-1]
        valid = {o["id"] for o in draft["payload"]["content"]["options"]} | {""}
        if recommended not in valid:
            raise WorkflowError("Рекомендований варіант має бути одним із варіантів довідки")
        version = sum(1 for e in self.record.entries if e["type"] == "brief_signed") + 1
        return self.record.append(
            id=f"B-{self.number}/v{version}", type="brief_signed", task=6, actor=who, accountable=who,
            refs=[draft["id"]],
            payload={"content": draft["payload"]["content"], "zone": st["zone"], "recommended": recommended,
                     "assessment": _require(assessment, "Потрібна оцінка аналітика"), "signed_by": who["name"]})

    def review_brief(self, who: dict, comment: str, dissent: str = "") -> dict:
        """Другий рецензент (обов'язковий у зоні Z4); окрема думка фіксується до G2."""
        authorize(who["role"], 6, need="A")
        st = self.state()
        self._open(st)
        signed = self._fresh_signed(st)
        if who["name"] == signed["payload"]["signed_by"]:
            raise WorkflowError("Другий рецензент не може бути автором довідки")
        n = sum(1 for r in st["reviews"] if signed["id"] in r["refs"]) + 1
        return self.record.append(
            id=f"{signed['id']}/r{n}", type="brief_reviewed", task=6, actor=who, accountable=who,
            refs=[signed["id"]], payload={"comment": _require(comment, "Потрібен висновок рецензента"),
                                          "dissent": dissent.strip() or None, "reviewer": who["name"]})

    @staticmethod
    def _fresh_signed(st: dict) -> dict:
        signed = st["signed"]
        if not signed or signed["seq"] < st["content_seq"]:
            raise WorkflowError("Потрібна чинна підписана довідка (докази або зона змінилися після підпису)")
        return signed

    # ---- G2: рішення (завдання 7) ----------------------------------------
    def decide(self, who: dict, option: str, rationale: str, relied: list[str], departure: str = "") -> dict:
        authorize(who["role"], 7, need="A")
        st = self.state()
        if st["decision"]:
            raise WorkflowError("Рішення у справі вже ухвалено")
        if not st["scope_ok"]:
            raise WorkflowError("Межі пошуку не затверджено")
        self._official(who, st)
        signed = self._fresh_signed(st)
        content = signed["payload"]["content"]
        reviews = [r for r in st["reviews"] if signed["id"] in r["refs"]]
        if autonomy.ZONES[st["zone"]]["second_reviewer"] and not reviews:
            raise WorkflowError("У зоні Z4 до рішення потрібен висновок другого рецензента із зафіксованою окремою думкою")
        if option not in {o["id"] for o in content["options"]} | {"none"}:
            raise WorkflowError("Потрібно обрати один із варіантів довідки або «none» (жоден)")
        in_brief = set(content["context"])
        for o in content["options"]:
            in_brief |= set(o["supporting"]) | set(o["dissenting"])
        relied = list(dict.fromkeys(relied))
        if not relied or not set(relied) <= in_brief:
            raise WorkflowError("Рішення має спиратися на підтверджені твердження з підписаної довідки")
        _require(rationale, "Потрібно зафіксувати обґрунтування рішення")
        recommended = signed["payload"]["recommended"]
        departs = bool(recommended) and option != recommended
        if departs:
            _require(departure, "Рішення відходить від оцінки аналітика: потрібно пояснити чому")
        return self.record.append(
            id=f"D-{self.number}", type="decision_taken", task=7, actor=who, accountable=who,
            refs=[signed["id"]] + relied + [r["id"] for r in reviews],
            payload={"option": option, "rationale": rationale, "relied": relied, "departs": departs,
                     "departure": departure, "recommended": recommended, "zone": st["zone"],
                     "dissent_on_record": [r["payload"]["dissent"] for r in reviews if r["payload"]["dissent"]]})

    # ---- завдання 8: міжвідомча передача доказів ---------------------------
    def approve_transfer(self, who: dict, partner: str, claims: list[str]) -> dict:
        authorize(who["role"], 8, need="A")
        st = self.state()
        self._official(who, st)
        self._fresh_signed(st)
        own = [c for c in claims if c in st["claims"] and not st["claims"][c]["reused"]]
        if not own or len(own) != len(claims):
            raise WorkflowError("Передавати можна лише власні твердження, підтверджені на G1")
        return self.record.append(
            id=f"TA-{self.number}.{len(st['transfer_approvals']) + 1}", type="transfer_approved", task=8,
            actor=who, accountable=who, refs=own,
            payload={"partner": _require(partner, "Потрібно назвати орган-отримувач"), "claims": own})

    def transfer(self, who: dict, approval: str) -> tuple[dict, str]:
        """Координатор відповідає за передачу, але не за зміст доказів."""
        authorize(who["role"], 8, need="R")
        st = self.state()
        approvals = {a["id"]: a for a in st["transfer_approvals"]}
        if approval not in approvals:
            raise WorkflowError("Немає такого дозволу на передачу")
        if any(approval in t["refs"] for t in st["transfers"]):
            raise WorkflowError("За цим дозволом докази вже передано")
        appr = approvals[approval]
        excerpt: dict[str, dict] = {}
        for cid in appr["payload"]["claims"]:
            for e in self.record.trace_back(cid):
                excerpt[e["id"]] = e
        bundle = {"format": BUNDLE_FORMAT, "from_agency": st["need"]["agency"], "case": self.number,
                  "partner": appr["payload"]["partner"], "claims": appr["payload"]["claims"],
                  "record_excerpt": sorted(excerpt.values(), key=lambda e: e["seq"])}
        bundle["bundle_hash"] = bundle_hash(bundle)
        path = os.path.join(self.desk.data_dir, "exports",
                            f"bundle-case{self.number:04d}-{len(st['transfers']) + 1}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(bundle, fh, ensure_ascii=False, indent=1)
        entry = self.record.append(
            id=f"T-{self.number}.{len(st['transfers']) + 1}", type="evidence_transferred", task=8, actor=who,
            accountable={"role": OFFICIAL, "name": appr["actor"]["name"]}, refs=[approval],
            payload={"partner": appr["payload"]["partner"], "claims": appr["payload"]["claims"],
                     "bundle_hash": bundle["bundle_hash"], "entries": len(bundle["record_excerpt"]),
                     "file": os.path.basename(path)})
        return entry, path

    def import_evidence(self, who: dict, bundle: dict, assign: dict[str, tuple[str, str]]) -> list[dict]:
        """Повторне використання доказів, перевірених іншим органом (пропозиція P6).

        ``assign``: ідентифікатор твердження в пакеті -> (варіант, supports/dissents).
        Аналітик-отримувач відповідає за застосовність, а не за повторну перевірку тексту.
        """
        authorize(who["role"], 5, need="A")
        st = self.state()
        self._open(st)
        problems = verify_bundle(bundle)
        if problems:
            raise WorkflowError("Пакет доказів не пройшов перевірку: " + "; ".join(problems))
        by_id = {e["id"]: e for e in bundle["record_excerpt"]}
        out = []
        count = sum(1 for c in st["claims"].values() if c["reused"])
        for cid in bundle["claims"]:
            if cid not in assign:
                continue
            option, stance = assign[cid]
            claim = by_id[cid]
            passage = by_id[claim["refs"][0]]
            source = by_id[passage["refs"][0]]
            meta = by_id[source["refs"][0]]
            count += 1
            out.append(self.record.append(
                id=f"C-{self.number}.x{count}", type="claim_imported", task=5, actor=who, accountable=who,
                refs=[f"N-{self.number}/ok"],
                payload={"statement": claim["payload"]["statement"], "location": claim["payload"]["location"],
                         "option": option, "stance": stance, "grade": claim["payload"].get("grade", ""),
                         "uncertainty": "Перевірено іншим органом; застосовність оцінив аналітик-отримувач.",
                         "modified": False, "index": None,
                         "origin": {"agency": bundle["from_agency"], "case": bundle["case"], "claim": cid,
                                    "passage": passage["id"], "verified_by": passage["payload"]["reader"],
                                    "source": meta["payload"]["record"]["title"],
                                    "identifier": meta["payload"]["record"].get("identifier"),
                                    "bundle_hash": bundle["bundle_hash"]}}))
        return out

    # ---- G3: перегляд постфактум (завдання 9) -----------------------------
    def reconstruct(self) -> dict:
        """Чи можна від рішення пройти назад до запиту для кожного твердження."""
        st = self.state()
        if not st["decision"]:
            return {"decision": None, "claims": [], "reconstructable": False}
        rows = []
        for cid in st["decision"]["payload"]["relied"]:
            chain = self.record.trace_back(cid)
            types = {e["type"] for e in chain}
            if st["claims"][cid]["reused"]:
                ok = bool(st["claims"][cid]["origin"]["bundle_hash"])
                missing = [] if ok else ["походження пакета"]
            else:
                needed = {"passage_verified": "фрагмент повного тексту", "provenance_checked": "перевірка походження",
                          "metadata_record": "запис метаданих", "query_run": "запит",
                          "scope_approved": "затверджені межі"}
                missing = [label for t, label in needed.items() if t not in types]
                ok = not missing
            rows.append({"claim": cid, "ok": ok, "missing": missing,
                         "chain": [e["id"] for e in chain]})
        return {"decision": st["decision"]["id"], "claims": rows,
                "reconstructable": bool(rows) and all(r["ok"] for r in rows)}

    def audit(self, who: dict, finding: str, corrections: str = "", rationale_clear: bool | None = None,
              blind_checked: int | None = None, blind_unsupported: int | None = None) -> dict:
        authorize(who["role"], 9, need="A")
        st = self.state()
        if not st["decision"]:
            raise WorkflowError("Перегляд постфактум проводять після ухвалення рішення")
        integrity = self.record.verify()
        rec = self.reconstruct()
        return self.record.append(
            id=f"A-{self.number}.{len(st['audits']) + 1}", type="audit_review", task=9, actor=who,
            accountable=who, refs=[st["decision"]["id"]],
            payload={"finding": _require(finding, "Потрібен висновок перегляду"), "corrections": corrections,
                     "integrity_ok": not integrity, "integrity_problems": integrity,
                     "reconstructable": rec["reconstructable"], "rationale_clear": rationale_clear,
                     "blind_checked": blind_checked, "blind_unsupported": blind_unsupported,
                     "entries_reviewed": len(self.record)})

    # ---- подання ---------------------------------------------------------
    def brief_markdown(self) -> str:
        st = self.state()
        entry = st["signed"] or (st["drafts"][-1] if st["drafts"] else None)
        if not entry:
            raise WorkflowError("Довідки ще немає")
        c, claims = entry["payload"]["content"], st["claims"]

        def line(cid: str) -> str:
            cl = claims[cid]
            where = (f"пакет {cl['origin']['agency']}, {cl['origin']['claim']}" if cl["reused"]
                     else st["sources"][cl["index"]]["record"]["title"])
            return f"- {cl['statement']} [{cid}; {where}; {cl['location']}]"

        out = [f"# Аналітична довідка {entry['id']}", "", f"**Питання:** {c['question']}",
               f"**Рішення, яке підтримується:** {c['decision']}", f"**Зона автономії:** Z{entry['payload']['zone']}", ""]
        for o in c["options"]:
            out += [f"## {o['id']}: {o['title']}", "", "Докази на підтримку:"]
            out += [line(x) for x in o["supporting"]] or ["- немає"]
            out += ["", "Докази проти:"] + ([line(x) for x in o["dissenting"]] or ["- немає"]) + [""]
        if c["context"]:
            out += ["## Контекст", ""] + [line(x) for x in c["context"]] + [""]
        out += ["## Невизначеність і прогалини", ""] + ([f"- {u}" for u in c["uncertainties"]] or ["- не зафіксовано"])
        if entry["type"] == "brief_signed":
            out += ["", "## Оцінка аналітика", "", entry["payload"]["assessment"],
                    f"\nРекомендований варіант: {entry['payload']['recommended'] or 'не визначено'}",
                    f"Підписав(-ла): {entry['payload']['signed_by']}, {entry['ts']}"]
        else:
            out += ["", "_Проєкт. Не підписано аналітиком._"]
        return "\n".join(out)


def _short(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def bundle_hash(bundle: dict) -> str:
    body = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    blob = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify_bundle(bundle: dict) -> list[str]:
    """Перевірка пакета органом-отримувачем: формат, геші записів, повнота ланцюжків."""
    problems = []
    if bundle.get("format") != BUNDLE_FORMAT:
        return ["невідомий формат пакета"]
    if bundle_hash(bundle) != bundle.get("bundle_hash"):
        problems.append("геш пакета не збігається")
    by_id = {e["id"]: e for e in bundle["record_excerpt"]}
    for e in bundle["record_excerpt"]:
        if _digest(e) != e.get("hash"):
            problems.append(f"{e['id']}: запис змінено")
        problems += [f"{e['id']}: бракує попередника {r}" for r in e["refs"] if r not in by_id]
    for cid in bundle["claims"]:
        if by_id.get(cid, {}).get("type") != "claim_confirmed":
            problems.append(f"{cid}: у пакеті немає підтвердженого твердження")
    return problems
