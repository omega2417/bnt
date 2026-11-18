"""Тести ключових гарантій моделі AAE. Запуск: python -m pytest  або  python -m unittest discover -s tests."""
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from datetime import date

from aae import autonomy, frameworks, roles
from aae.agents import AppraisalAgent, DiscoveryAgent, ProvenanceAgent, load_catalog
from aae.config import default_config
from aae.demo import (ANALYST_1, ANALYST_2, AUDITOR, COORD, OFFICIAL_1, scenario_training,
                      scenario_transposition)
from aae.indicators import case_indicators, recall_precision
from aae.record import DecisionRecord, RecordError
from aae.roles import AGENT, ANALYST, OFFICIAL, NotPermitted
from aae.workflow import Desk, WorkflowError, actor, verify_bundle

TODAY = date(2026, 11, 18)


def new_desk():
    return Desk(tempfile.mkdtemp(prefix="aae-test-"), today=TODAY)


def open_case(desk, consequence="tactical", uncertainty="moderate", triggers=None):
    case = desk.create_case(ANALYST_1, question="Питання?", decision="Рішення", options=["Так", "Ні"],
                            consequence=consequence, uncertainty=uncertainty, jurisdictions=["UA"],
                            official=OFFICIAL_1["name"], triggers=triggers)
    case.approve_scope(OFFICIAL_1)
    return case


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "r.jsonl")
        self.rec = DecisionRecord(self.path)
        self.human = {"role": ANALYST, "name": "А"}
        self.rec.append(id="N-1", type="need_defined", actor=self.human, accountable=self.human)
        self.rec.append(id="Q-1", type="query_run", actor={"role": AGENT, "name": "agent"},
                        accountable=self.human, refs=["N-1"])

    def test_chain_is_valid_and_reloads(self):
        self.assertEqual(self.rec.verify(), [])
        self.assertEqual(len(DecisionRecord(self.path)), 2)

    def test_agent_can_never_be_accountable(self):
        with self.assertRaises(RecordError):
            self.rec.append(id="X", type="t", actor=self.human, accountable={"role": AGENT, "name": "agent"})

    def test_accountable_person_must_be_named(self):
        with self.assertRaises(RecordError):
            self.rec.append(id="X", type="t", actor=self.human, accountable={"role": ANALYST, "name": ""})

    def test_append_only_and_refs_must_exist(self):
        with self.assertRaises(RecordError):
            self.rec.append(id="Q-1", type="t", actor=self.human, accountable=self.human)
        with self.assertRaises(RecordError):
            self.rec.append(id="Y", type="t", actor=self.human, accountable=self.human, refs=["nope"])

    def _rewrite(self, mutate):
        lines = [json.loads(l) for l in open(self.path, encoding="utf-8")]
        lines = mutate(lines)
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(l, ensure_ascii=False) + "\n" for l in lines)
        return DecisionRecord(self.path).verify()

    def test_tampering_is_detected(self):
        def edit(lines):
            lines[0]["payload"] = {"changed": True}
            return lines
        self.assertTrue(any("змінено" in p for p in self._rewrite(edit)))

    def test_deletion_is_detected(self):
        self.assertTrue(self._rewrite(lambda lines: lines[1:]))

    def test_trace_back_reaches_origin(self):
        self.assertEqual([e["id"] for e in self.rec.trace_back("Q-1")], ["Q-1", "N-1"])


class RolesAndAutonomyTests(unittest.TestCase):
    def test_raci_matches_publication(self):
        for task, (_, _, raci) in roles.TASKS.items():
            self.assertNotEqual(raci.get(AGENT), "A")
            self.assertEqual(list(raci.values()).count("A"), 1)
        self.assertEqual(roles.raci(5, AGENT), "C")      # на G1 агент лише консультує
        self.assertEqual(roles.raci(10, AGENT), "")      # агент не змінює власні правила
        with self.assertRaises(NotPermitted):
            roles.authorize(AGENT, 7)
        with self.assertRaises(NotPermitted):
            roles.authorize(ANALYST, 7, need="A")

    def test_zones_follow_figure_5_examples(self):
        z = autonomy.base_zone
        self.assertEqual(z("routine", "low"), 1)            # a: тижневий дайджест
        self.assertEqual(z("tactical", "moderate"), 2)      # b: перелік пріоритетів оновлень
        self.assertEqual(z("institutional", "moderate"), 3) # c: варіанти транспозиції NIS2
        self.assertEqual(z("strategic", "high"), 4)         # d: національний план реагування
        self.assertEqual(z("strategic", "low"), 3)          # e: стратегічне питання, усталені докази

    def test_triggers_escalate_one_zone_capped(self):
        self.assertEqual(autonomy.effective_zone("routine", "low", ["novel_threat"]), 2)
        self.assertEqual(autonomy.effective_zone("strategic", "high", ["classified"]), 4)
        with self.assertRaises(ValueError):
            autonomy.effective_zone("routine", "low", ["bogus"])

    def test_agent_latitude_shrinks(self):
        allowed = [set(autonomy.ZONES[z]["agent_functions"]) for z in (1, 2, 3, 4)]
        for wider, narrower in zip(allowed, allowed[1:]):
            self.assertTrue(narrower <= wider)
        self.assertEqual(allowed[3], {"F1"})
        autonomy.validate_matrix(autonomy.DEFAULT_MATRIX)
        bad = {u: dict(row) for u, row in autonomy.DEFAULT_MATRIX.items()}
        bad["high"]["strategic"] = 1
        with self.assertRaises(ValueError):
            autonomy.validate_matrix(bad)


class FrameworkTests(unittest.TestCase):
    def test_coding_reproduces_published_findings(self):
        self.assertEqual(frameworks.explicit_count("E5"), 7)   # E5 явно в усіх семи
        self.assertEqual(frameworks.explicit_count("E1"), 6)   # E1 явно в шести
        self.assertEqual(frameworks.explicit_count("E7"), 0)   # E7 ніде не закріплено явно
        for e in ("E2", "E4"):                                 # лише в трьох актах про ШІ
            self.assertEqual([d for d in frameworks.DOCUMENTS if frameworks.CODING[e][d][0] == "E"],
                             ["D2", "D4", "D6"])
        self.assertEqual(frameworks.coverage_by_document(),
                         {"D1": 4.5, "D3": 4.5, "D5": 2.5, "D7": 5.0, "D2": 7.0, "D4": 7.0, "D6": 6.5})


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.by_key = {r["key"]: r for r in self.catalog["records"]}
        self.prov = ProvenanceAgent(self.catalog, default_config()["trusted_issuers"])

    def test_discovery_deduplicates_by_identifier(self):
        found = DiscoveryAgent(self.catalog).search(["csf"])
        keys = [r["record"]["key"] for r in found["results"]]
        self.assertIn("csf2", keys)
        self.assertNotIn("csf2-crossref", keys)
        self.assertEqual(found["duplicates"][0]["dropped"], "csf2-crossref")

    def test_provenance_statuses(self):
        self.assertTrue(self.prov.check(self.by_key["nis2"])["usable"])
        repealed = self.prov.check(self.by_key["nis1"])
        self.assertFalse(repealed["usable"])
        self.assertEqual(repealed["current_version"]["key"], "nis2")
        unresolved = self.prov.check(self.by_key["demo-report"])
        self.assertFalse(unresolved["resolved"])
        self.assertTrue(unresolved["flags"])              # позначено, а не відкинуто мовчки

    def test_every_real_record_resolves(self):
        for record in self.catalog["records"]:
            if not record["synthetic"]:
                result = self.prov.check(record)
                self.assertTrue(result["resolved"] and result["issuer_verified"], record["key"])

    def test_issuer_mismatch_is_flagged(self):
        fake = dict(self.by_key["nis2"], issuer="Невідомий видавець")
        self.assertFalse(self.prov.check(fake)["issuer_verified"])

    def test_appraisal_states_uncertainty_and_suggests_trigger(self):
        rating = AppraisalAgent(5, TODAY).rate(self.by_key["nis2"], self.prov.check(self.by_key["nis2"]),
                                               {"jurisdictions": ["UA"]})
        self.assertTrue(rating["uncertainty"])
        self.assertEqual(rating["suggested_triggers"], ["cross_jurisdiction"])


class WorkflowTests(unittest.TestCase):
    def test_nothing_before_scope_approval_and_only_named_official(self):
        desk = new_desk()
        case = desk.create_case(ANALYST_1, question="Q", decision="D", options=["a", "b"], consequence="tactical",
                                uncertainty="low", jurisdictions=["UA"], official=OFFICIAL_1["name"])
        with self.assertRaises(WorkflowError):
            case.run_discovery(ANALYST_1, ["nis2"])
        with self.assertRaises(WorkflowError):
            case.approve_scope(actor(OFFICIAL, "Інша особа"))
        with self.assertRaises(NotPermitted):
            case.approve_scope(ANALYST_1)
        with self.assertRaises(NotPermitted):
            desk.create_case(OFFICIAL_1, question="Q", decision="D", options=["a", "b"], consequence="tactical",
                             uncertainty="low", jurisdictions=["UA"], official=OFFICIAL_1["name"])

    def test_g1_gate_blocks_brief_and_requires_reason_and_location(self):
        case = open_case(new_desk())
        case.run_discovery(ANALYST_1, ["навчання", "керівні органи"])
        case.run_provenance(ANALYST_1)
        case.run_appraisal(ANALYST_1)
        candidates = case.propose_claims(ANALYST_1)
        self.assertTrue(candidates)
        with self.assertRaises(WorkflowError):
            case.draft_brief(ANALYST_1)                      # жодне твердження не перевірено
        kid = candidates[0]["id"]
        with self.assertRaises(WorkflowError):
            case.verify_claim(ANALYST_1, kid, "accept", reason="", location="Art. 20(2)")
        with self.assertRaises(WorkflowError):
            case.verify_claim(ANALYST_1, kid, "accept", reason="прочитано", location="")
        with self.assertRaises(NotPermitted):
            case.verify_claim(OFFICIAL_1, kid, "accept", reason="x", location="y")
        case.verify_claim(ANALYST_1, kid, "accept", reason="прочитано", location="Art. 20(2)", option="opt1")
        with self.assertRaises(WorkflowError):
            case.draft_brief(ANALYST_1)                      # у Z2 потрібно перевірити всі
        for c in candidates[1:]:
            case.verify_claim(ANALYST_1, c["id"], "reject", reason="не підтверджено текстом")
        draft = case.draft_brief(ANALYST_1)
        self.assertEqual(draft["actor"]["role"], AGENT)      # у Z2 проєкт складає агент
        self.assertEqual(draft["accountable"]["role"], ANALYST)
        self.assertEqual(case_indicators(case)["traceability_rate"], 1.0)

    def test_unusable_source_cannot_support_a_claim(self):
        case = open_case(new_desk(), "institutional", "moderate")
        case.run_discovery(ANALYST_1, ["nis", "транспозиція"])
        case.run_provenance(ANALYST_1)
        st = case.state()
        self.assertEqual(st["zone"], 4)                      # нерозв'язане джерело підняло зону
        self.assertIn("provenance_unresolved", st["triggers"])
        idx = {s["record"]["key"]: i for i, s in st["sources"].items()}
        kid = case.add_claim(ANALYST_1, idx["nis1"], "Твердження зі скасованої директиви")["id"]
        with self.assertRaises(WorkflowError):
            case.verify_claim(ANALYST_1, kid, "accept", reason="x", location="Art. 1")

    def test_zone_limits_agents(self):
        case = open_case(new_desk(), "strategic", "high")     # Z4
        case.run_discovery(ANALYST_1, ["nis2"])
        for call in (case.run_provenance, case.run_appraisal, case.propose_claims):
            with self.assertRaises(WorkflowError):
                call(ANALYST_1)
        case.record_provenance(ANALYST_1, 1, resolved=True, issuer_verified=True, status="current",
                               note="звірено з EUR-Lex")
        self.assertEqual(case.state()["sources"][1]["prov"]["actor"]["role"], ANALYST)

    def test_z1_sampled_audit(self):
        case = open_case(new_desk(), "routine", "low")
        self.assertEqual(case.state()["zone"], 1)
        case.run_discovery(ANALYST_1, ["навчання", "керівні органи"])
        case.run_provenance(ANALYST_1)
        candidates = case.propose_claims(ANALYST_1)
        status = case.g1_status()
        self.assertLess(status["required"], status["total"])
        for c in candidates[:status["required"]]:
            case.verify_claim(ANALYST_1, c["id"], "accept", reason="прочитано", location="Art.", option="opt1")
        case.draft_brief(ANALYST_1)
        rate = case_indicators(case)["traceability_rate"]
        self.assertTrue(0 < rate < 1)                        # неперевірені твердження видно в показнику

    def test_full_scenarios_decision_rules_and_reuse(self):
        desk = new_desk()
        case1, bundle_path = scenario_training(desk)
        self.assertEqual(case1.record.verify(), [])
        ind = case_indicators(case1)
        self.assertEqual((ind["g1_accept"], ind["g1_modify"], ind["g1_reject"]), (6, 1, 1))
        self.assertTrue(ind["reconstructable"])
        with self.assertRaises(WorkflowError):
            case1.run_discovery(ANALYST_1, ["nis2"])         # після рішення докази не змінюються
        with open(bundle_path, encoding="utf-8") as fh:
            bundle = json.load(fh)
        self.assertEqual(verify_bundle(bundle), [])
        tampered = json.loads(json.dumps(bundle))
        tampered["record_excerpt"][-1]["payload"]["statement"] = "підмінено"
        self.assertTrue(verify_bundle(tampered))
        case2 = scenario_transposition(desk, bundle_path)
        ind2 = case_indicators(case2)
        self.assertEqual((ind2["zone"], ind2["reused_claims"]), (4, 2))
        self.assertTrue(case2.state()["decision"]["payload"]["dissent_on_record"])
        chain = [e["type"] for e in case2.record.trace_back("D-2")]
        for needed in ("brief_signed", "claim_confirmed", "passage_verified", "provenance_checked",
                       "metadata_record", "query_run", "need_defined"):
            self.assertIn(needed, chain)

    def _ready_for_decision(self, consequence, uncertainty):
        case = open_case(new_desk(), consequence, uncertainty)
        case.run_discovery(ANALYST_1, ["керівні органи"])     # знаходить лише NIS2
        zone = case.state()["zone"]
        if zone == 4:
            case.record_provenance(ANALYST_1, 1, resolved=True, issuer_verified=True, status="current", note="EUR-Lex")
        else:
            case.run_provenance(ANALYST_1)
        kid = case.add_claim(ANALYST_1, 1, "Керівні органи затверджують заходи.")["id"]
        case.verify_claim(ANALYST_1, kid, "accept", reason="прочитано", location="Art. 20(1)", option="opt1")
        case.draft_brief(ANALYST_1)
        case.sign_brief(ANALYST_1, "Рекомендую перший варіант.", "opt1")
        return case, "C-" + kid[2:]

    def test_decision_requires_rationale_relied_claims_and_departure(self):
        case, claim = self._ready_for_decision("tactical", "low")
        with self.assertRaises(NotPermitted):
            case.decide(ANALYST_1, "opt1", "бо так", [claim])
        with self.assertRaises(WorkflowError):
            case.decide(OFFICIAL_1, "opt1", "", [claim])
        with self.assertRaises(WorkflowError):
            case.decide(OFFICIAL_1, "opt1", "бо так", [])
        with self.assertRaises(WorkflowError):
            case.decide(OFFICIAL_1, "opt2", "бо так", [claim])          # відхід без пояснення
        entry = case.decide(OFFICIAL_1, "opt2", "бо так", [claim], departure="Бюджетні обмеження")
        self.assertTrue(entry["payload"]["departs"])
        with self.assertRaises(NotPermitted):
            case.audit(OFFICIAL_1, "сам себе перевірив")
        self.assertTrue(case.audit(AUDITOR, "ок")["payload"]["reconstructable"])

    def test_z4_needs_independent_second_reviewer(self):
        case, claim = self._ready_for_decision("strategic", "high")
        with self.assertRaises(WorkflowError):
            case.decide(OFFICIAL_1, "opt1", "обґрунтування", [claim])
        with self.assertRaises(WorkflowError):
            case.review_brief(ANALYST_1, "сам себе")
        case.review_brief(ANALYST_2, "перевірено", dissent="маю окрему думку")
        self.assertEqual(case.decide(OFFICIAL_1, "opt1", "обґрунтування", [claim])["payload"]["dissent_on_record"],
                         ["маю окрему думку"])

    def test_escalation_after_signature_invalidates_brief(self):
        case, claim = self._ready_for_decision("tactical", "low")
        case.raise_trigger(ANALYST_1, "novel_threat")
        with self.assertRaises(WorkflowError):
            case.decide(OFFICIAL_1, "opt1", "обґрунтування", [claim])

    def test_transfer_roles(self):
        case, claim = self._ready_for_decision("tactical", "low")
        with self.assertRaises(NotPermitted):
            case.approve_transfer(COORD, "Партнер", [claim])
        approval = case.approve_transfer(OFFICIAL_1, "Партнер", [claim])
        with self.assertRaises(NotPermitted):
            case.transfer(ANALYST_1, approval["id"])
        entry, path = case.transfer(COORD, approval["id"])
        self.assertEqual(entry["accountable"]["role"], OFFICIAL)
        self.assertTrue(os.path.exists(path))

    def test_config_revision_is_recorded_and_closed_to_agents(self):
        desk = new_desk()
        with self.assertRaises(NotPermitted):
            desk.revise_config(actor(AGENT, "agent"), OFFICIAL_1, {"z1_sample_rate": 0.5}, "причина")
        with self.assertRaises(NotPermitted):
            desk.revise_config(ANALYST_1, ANALYST_2, {"z1_sample_rate": 0.5}, "причина")
        with self.assertRaises(WorkflowError):
            desk.revise_config(ANALYST_1, OFFICIAL_1, {"autonomy_matrix": {}}, "причина")
        desk.revise_config(ANALYST_1, OFFICIAL_1, {"z1_sample_rate": 0.5}, "посилення контролю")
        reloaded = Desk(desk.data_dir)
        self.assertEqual((reloaded.config["version"], reloaded.config["z1_sample_rate"]), (2, 0.5))
        self.assertEqual(reloaded.system.entries[0]["payload"]["before"], {"z1_sample_rate": 0.25})


class IndicatorAndWebTests(unittest.TestCase):
    def test_recall_precision(self):
        result = recall_precision(["a", "b", "c", "d"], ["a", "b", "x"])
        self.assertAlmostEqual(result["recall"], 2 / 3)
        self.assertAlmostEqual(result["precision"], 0.5)

    def test_web_pages_render(self):
        from http.server import HTTPServer
        from aae.web import App, make_handler
        desk = new_desk()
        scenario_training(desk)
        server = HTTPServer(("127.0.0.1", 0), make_handler(App(desk.data_dir)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            for path, text in [("/", "Справи"), ("/case/1", "Журнал рішень"), ("/model", "RACI"),
                               ("/frameworks", "Індекс покриття"), ("/config", "Версія конфігурації"),
                               ("/new", "Нова справа")]:
                body = urllib.request.urlopen(base + path).read().decode("utf-8")
                self.assertIn(text, body, path)
            self.assertEqual(len(json.load(urllib.request.urlopen(base + "/case/1/record.json"))), len(desk.case(1).record))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
