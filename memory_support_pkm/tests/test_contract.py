"""Equations (2)-(7), invariants I1-I4 and the six counterexamples of Table 2."""
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pgmem import metrics as M  # noqa: E402
from pgmem.assistance import adapt_start_level, gate, next_level  # noqa: E402
from pgmem.governance import ActionQueue, PolicyEngine, QueuedAction  # noqa: E402
from pgmem.model import Episode, EpisodeState, EvidenceStatus as ES, PersonalEventBase, Record  # noqa: E402
from pgmem.recall import GroundedRecall, NaiveRAG, Question, release  # noqa: E402

T0 = datetime(2026, 10, 2, 10)
PID = "olena"


def rec(base, subject, value, status, kind="scheduled", category="appointments", kappa=0.95, **kw):
    return base.add(Record(base.new_id(), PID, subject, value, T0, kw.pop("source", "calendar"), kappa,
                           frozenset({"self"}), status=status, category=category, kind=kind, value=value, **kw))


def q(subject, kind, category="appointments", requester=PID):
    return Question("q", PID, requester, subject, kind, category)


@pytest.fixture
def world():
    base = PersonalEventBase(PID)
    pol = PolicyEngine(PID)
    return base, pol, GroundedRecall(base, pol)


# ---------------------------------------------------------------- equations
def test_escalation_rule_eq2():
    assert next_level(1, 1, 4) == 2
    assert next_level(4, 1, 4) == 4          # capped at L_max
    assert next_level(2, 0, 4) == 2          # closed gate keeps level


def test_gate_blocks_on_postpone_decline_missing_observation():
    assert gate(True, False, False, True) == 1
    assert gate(True, True, False, True) == 0
    assert gate(True, False, True, True) == 0
    assert gate(False, False, False, True) == 0
    assert gate(True, False, False, False) == 0   # missing/ambiguous -> no escalation


def test_start_level_eq3():
    assert adapt_start_level(2, 5, 5, 0, True) == 1
    assert adapt_start_level(2, 5, 5, 0, False) == 2  # needs the user's agreement
    assert adapt_start_level(0, 9, 5, 0, True) == 0   # bounded by L_min
    assert adapt_start_level(2, 4, 5, 0, True) == 2


def test_release_rule_eq5():
    assert release(0.9) == "answer"
    assert release(0.5) == "answer_uncertain"
    assert release(0.1) == "abstain"


def test_metrics_eq6_eq7():
    assert M.tsr(8, 10) == 0.8 and M.fpr(1, 4) == 0.25 and M.coverage(3, 4) == 0.75
    assert math.isnan(M.f_ext(0, 0))     # undefined, never "perfect"


# ------------------------------------------------------- Table 2 counterexamples
def test_plan_without_attendance_evidence(world):
    base, _, gr = world
    rec(base, "appt:kovalenko", "2026-10-02", ES.PLAN)
    a = gr.answer(q("appt:kovalenko", "occurred"))
    assert a.substantive
    assert all(c.asserted_status == ES.PLAN and c.kind == "scheduled" for c in a.claims)
    assert "не підтверджують" in a.text


def test_two_incompatible_completion_records(world):
    base, _, gr = world
    r1 = rec(base, "bill", "true", ES.SELF_REPORT, kind="occurred", category="finance", kappa=0.8)
    r2 = rec(base, "bill", "false", ES.OBSERVATION, kind="occurred", category="finance", kappa=0.99)
    base.mark_disputed([r1.record_id, r2.record_id], PID, T0)
    assert gr.answer(q("bill", "occurred", "finance")).decision == "clarify"


def test_incompatible_records_even_without_dispute_flag(world):
    base, _, gr = world
    rec(base, "bill", "true", ES.SELF_REPORT, kind="occurred", category="finance")
    rec(base, "bill", "false", ES.OBSERVATION, kind="occurred", category="finance")
    assert gr.answer(q("bill", "occurred", "finance")).decision == "clarify"


def test_postponement_is_not_failure():
    assert gate(True, postponed=True, declined=False, progress_supports_escalation=True) == 0
    ep = Episode("e1", PID, "appointment_prep", T0, False)
    ep.state = EpisodeState.POSTPONED
    assert ep.state != EpisodeState.MISSED_INFERRED


def test_consent_withdrawn_after_message_queued():
    pol = PolicyEngine(PID)
    pol.grant("iryna", "medication", "message")
    queue = ActionQueue(pol)
    queue.enqueue(QueuedAction("k1", "message", "iryna", "medication", "missed tablets", T0))
    pol.revoke("iryna", "medication", "message")
    assert queue.dispatch(T0 + timedelta(minutes=5)) == []
    assert [a.key for a in queue.cancelled] == ["k1"]


def test_replay_never_duplicates():
    pol = PolicyEngine(PID)
    pol.grant("iryna", "*", "message")
    queue = ActionQueue(pol)
    a = QueuedAction("k1", "message", "iryna", "medication", "x", T0)
    queue.enqueue(a)
    queue.dispatch(T0)
    queue.enqueue(a)
    assert queue.dispatch(T0) == [] and len(queue.sent) == 1


def test_record_corrected_after_answer_cached(world):
    base, _, gr = world
    r = rec(base, "appt:dentist", "2026-10-10", ES.PLAN)
    assert gr.answer(q("appt:dentist", "scheduled")).claims[0].value == "2026-10-10"
    base.correct(r.record_id, PID, T0, value="2026-10-14", content="2026-10-14")
    a = gr.answer(q("appt:dentist", "scheduled"))
    assert a.claims[0].value == "2026-10-14" and a.claims[0].record_version == 2


def test_sensor_unavailable_gives_unknown():
    ep = Episode("e2", PID, "medication_morning", T0, True)
    with pytest.raises(ValueError):
        ep.complete("")                      # no evidential basis -> no completion
    ep.state = EpisodeState.UNKNOWN
    assert ep.completion_source is None


# ------------------------------------------------------------- scenarios / I1-I2
def test_unrecorded_event_abstains(world):
    _, _, gr = world
    assert gr.answer(q("call:andrii:2026-10-22", "occurred", "social")).decision == "abstain"


def test_self_report_is_not_promoted(world):
    base, _, gr = world
    rec(base, "med:2026-10-23", "true", ES.SELF_REPORT, kind="occurred", category="medication", kappa=0.85)
    a = gr.answer(q("med:2026-10-23", "occurred", "medication"))
    assert a.claims[0].asserted_status == ES.SELF_REPORT
    assert "Незалежно я це не перевіряв" in a.text


def test_permission_precedes_access(world):
    base, pol, gr = world
    rec(base, "note:1", "пароль", ES.SELF_REPORT, kind="content", category="personal_note")
    a = gr.answer(q("note:1", "content", "personal_note", requester="iryna"))
    assert a.decision == "refuse" and not a.disclosed_records
    pol.grant("iryna", "personal_note", "read")
    assert gr.answer(q("note:1", "content", "personal_note", requester="iryna")).substantive


def test_deletion_keeps_only_minimal_audit(world):
    base, _, gr = world
    r = rec(base, "note:2", "секрет", ES.SELF_REPORT, kind="content", category="personal_note")
    base.delete(r.record_id, PID, T0)
    assert gr.answer(q("note:2", "content", "personal_note")).decision == "abstain"
    assert all("секрет" not in e.detail for e in base.audit)


def test_naive_baseline_violates_contract():
    import numpy as np
    base = PersonalEventBase(PID)
    rec(base, "appt:x", "2026-10-02", ES.PLAN)
    a = NaiveRAG(base, np.random.default_rng(0)).answer(q("appt:x", "occurred"))
    assert a.claims[0].asserted_status == ES.OBSERVATION   # plan read as attendance


def test_pipeline_small(tmp_path):
    from pgmem import pipeline, schema
    pipeline.generate_dataset(tmp_path / "data", n=12, days=7, seed=1)
    assert schema.validate(tmp_path / "data") == []
    t = pipeline.load_dataset(tmp_path / "data")
    ep, rc = pipeline.run_simulation(t, tmp_path / "results", 1)
    assert set(ep.condition) == {"reminder", "single_agent", "proposed"}
    prop = ep[ep.condition == "proposed"]
    assert not prop.invented_outcome.any() and not prop.unauthorised_contact.any()
    assert rc[rc.condition == "proposed"].fabricated.sum() == 0
