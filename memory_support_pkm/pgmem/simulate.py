"""Comparative simulation on identical synthetic histories (Section 6).

Conditions: ``reminder`` (fixed reminder interface), ``single_agent``
(retrieval assistant that escalates on timeouts and infers outcomes from
missing data) and ``proposed`` (the action-and-evidence contract).
Person behaviour uses common random numbers, so the three conditions
face exactly the same simulated people and days.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from .assistance import adapt_start_level, gate, next_level
from .governance import PolicyEngine
from .model import STATUS_STRENGTH, SUPPORTS, EvidenceStatus, PersonalEventBase, Record
from .recall import GroundedRecall, NaiveRAG, Question, ReminderOnly, noisy_sup

CONDITIONS = ["reminder", "single_agent", "proposed"]
MAX_PROMPTS = 4
P_POSTPONE, P_DECLINE, P_DEVICE_DOWN, P_WITHDRAWN = 0.07, 0.03, 0.04, 0.08
M_ADAPT, L_MIN = 5, 0


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _respond(u: float, level: int, a: float) -> str:
    p_c = 0.8 if level >= 4 else float(_sigmoid(-1.4 + 0.7 * level + 0.9 * a))
    if u < p_c:
        return "complete"
    u -= p_c
    if u < P_POSTPONE:
        return "postpone"
    u -= P_POSTPONE
    if u < P_DECLINE:
        return "decline"
    rest = 1 - p_c - P_POSTPONE - P_DECLINE
    return "needs_help" if u < rest / 2 else "no_response"


def simulate_episodes(cohort: pd.DataFrame, episodes: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(episodes)
    draws = dict(
        before=rng.random(n), known_before=rng.random(n), sr=rng.random(n), sensor=rng.random(n),
        withdrawn=rng.random(n), resp=rng.random((n, MAX_PROMPTS + 1)), dev=rng.random((n, MAX_PROMPTS + 1)),
    )
    people = cohort.set_index("participant_id")
    out = []
    for cond in CONDITIONS:
        start_level: dict[tuple[str, str], int] = {}
        streak: dict[tuple[str, str], int] = {}
        for i, ep in enumerate(episodes.itertuples()):
            p = people.loc[ep.participant_id]
            a = p.ability_latent
            p_sr = float(_sigmoid(0.3 + 0.8 * a))
            detected = bool(ep.sensorable and draws["sensor"][i] < 0.85)
            reports = draws["sr"][i] < p_sr
            withdrawn = draws["withdrawn"][i] < P_WITHDRAWN
            l_max = 4 if p.has_trusted_person else 3
            key = (ep.participant_id, ep.task_type)
            s0 = start_level.get(key, 1) if cond == "proposed" else 1

            done = draws["before"][i] < float(_sigmoid(-0.6 + 0.9 * a))
            completion_level = 0 if done else None
            known = None
            if done and detected and cond != "reminder":
                known = "sensor"
            elif done and draws["known_before"][i] < 0.4 * p_sr:
                known = "self_report"

            prompts = false_prompts = missed = escalations = 0
            unauthorised = cancelled = False
            level, max_level = s0, s0
            postponed = declined = resumed = ignored_decline = False
            k = 0
            while known is None and k < MAX_PROMPTS and not declined:
                if postponed:
                    if cond == "proposed":
                        if resumed:
                            break
                        resumed = True       # the user's chosen resumption rule: one later prompt
                        postponed = False
                    elif cond == "reminder":
                        postponed = False    # snooze -> next reminder is the resumption
                if level == 0:
                    # L0: context retained, no prompt; progress check before L1.
                    level = 1
                    max_level = max(max_level, 1)
                    continue
                if level == 4:
                    if cond == "proposed" and withdrawn:
                        cancelled = True     # I1: recheck at dispatch -> cancel
                        level = 3
                        l_max = 3
                        continue
                    if withdrawn:
                        unauthorised = True
                if draws["dev"][i, k] < P_DEVICE_DOWN:
                    missed += 1
                    k += 1
                    continue
                prompts += 1
                max_level = max(max_level, level)
                if done or postponed or ignored_decline:
                    false_prompts += 1
                k += 1
                if done:
                    if draws["resp"][i, k - 1] < p_sr:
                        known = "self_report"   # "Have you already...?" -> "yes"
                    continue
                r = _respond(draws["resp"][i, k - 1], level, a)
                if r == "complete":
                    done, completion_level = True, level
                    if reports:
                        known = "self_report"
                    elif detected and cond != "reminder":
                        known = "sensor"
                    continue
                if r == "postpone":
                    postponed = True
                    if cond == "single_agent":   # treats the delay as failure and escalates
                        new = next_level(level, 1, l_max)
                        escalations += new > level
                        level = new
                    continue
                if r == "decline":
                    declined = cond != "reminder"
                    ignored_decline = cond == "reminder"  # the reminder app keeps reminding
                    continue
                if cond == "reminder":
                    continue                  # fixed L1, no escalation
                if cond == "single_agent":
                    g = 1                     # timeout alone triggers escalation
                else:
                    g = gate(permission_ok=True, postponed=postponed, declined=declined,
                             progress_supports_escalation=(r == "needs_help"))
                new = next_level(level, g, l_max)
                escalations += new > level
                level = new

            # Recorded state of the episode
            if known:
                state, source = "completed", known
            elif declined:
                state, source = "declined", "user"
            elif postponed and cond == "proposed":
                state, source = "postponed", "user"
            elif cond == "proposed":
                state, source = "unknown", ""
            else:
                state, source = "missed_inferred", ""  # silence converted to failure (violates I3)

            if cond == "proposed":
                if state == "completed" and escalations == 0:
                    streak[key] = streak.get(key, 0) + 1
                else:
                    streak[key] = 0
                if not ep.safety_critical:
                    new_start = adapt_start_level(s0, streak[key], M_ADAPT, L_MIN, bool(p.agrees_to_level_reduction))
                    if new_start != s0:
                        streak[key] = 0
                    start_level[key] = new_start

            out.append(dict(
                condition=cond, episode_id=ep.episode_id, participant_id=ep.participant_id,
                task_type=ep.task_type, safety_critical=ep.safety_critical, day=ep.day,
                start_level=s0, max_level=max_level, prompts=prompts, false_prompts=false_prompts,
                missed_prompts=missed, escalations=escalations, completed_true=done,
                completion_level=completion_level, recorded_state=state, evidence_source=source,
                invented_outcome=state == "missed_inferred",
                wrong_failure=(state == "missed_inferred") and done,
                unauthorised_contact=unauthorised, contact_cancelled=cancelled,
            ))
    return pd.DataFrame(out)


# --------------------------------------------------------------------- recall
def _to_record(row) -> Record:
    return Record(
        record_id=row.record_id, person_id=row.person_id, subject=row.subject, content=row.content,
        time=datetime.fromisoformat(row.time), source=row.source, kappa=float(row.kappa),
        scope=frozenset(str(row.scope).split(",")), version=int(row.version),
        status=EvidenceStatus(row.status), category=row.category, kind=row.kind, value=str(row.value),
        supersedes=row.supersedes or None, active=bool(row.active), disputed=bool(row.disputed),
    )


def build_event_base(person_id: str, records: pd.DataFrame) -> PersonalEventBase:
    base = PersonalEventBase(person_id)
    for row in records[records.person_id == person_id].fillna({"supersedes": ""}).itertuples():
        base.add(_to_record(row), actor=row.source)
    return base


def build_policy(person_id: str) -> PolicyEngine:
    pol = PolicyEngine(person_id)
    trusted = f"trusted:{person_id}"
    pol.grant(trusted, "medication", "read")      # e.g. missed safety-critical tasks
    pol.grant(trusted, "medication", "message")
    return pol


def _ext_supported(claim, ref: dict) -> bool:
    if claim.kind == "occurred" and claim.asserted_status == EvidenceStatus.SELF_REPORT:
        return ref.get((claim.subject, "reported")) == claim.value
    return ref.get((claim.subject, claim.kind)) == claim.value


def simulate_recall(cohort, records, questions, reference, seed: int = 13) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = []
    for pid in cohort.participant_id:
        recs = records[records.person_id == pid]
        ref = {(r.subject, r.kind): str(r.value) for r in reference[reference.person_id == pid].itertuples()}
        base = build_event_base(pid, recs)
        policy = build_policy(pid)
        by_id = {r.record_id: r for r in base.all(include_inactive=True)}
        assistants = {
            "reminder": ReminderOnly(),
            "single_agent": NaiveRAG(base, np.random.default_rng(rng.integers(1 << 31))),
            "proposed": GroundedRecall(base, policy, sup=noisy_sup(np.random.default_rng(rng.integers(1 << 31))),
                                       identity_confusion=0.03, rng=np.random.default_rng(rng.integers(1 << 31))),
        }
        for q in questions[questions.person_id == pid].itertuples():
            question = Question(q.question_id, pid, q.requester, q.subject, q.kind, q.category, q.text)
            for cond, asst in assistants.items():
                ans = asst.answer(question)
                n_sup = n_fab = n_over = n_stale = n_wrong = 0
                for c in ans.claims:
                    if c.subject != q.subject:
                        n_wrong += 1          # accurate record, wrong question: unsupported
                    else:
                        n_sup += _ext_supported(c, ref)
                    if c.record_id is None:
                        n_fab += 1
                        continue
                    r = by_id[c.record_id]
                    n_over += r.status not in SUPPORTS.get(c.asserted_status, set()) or \
                        STATUS_STRENGTH.get(c.asserted_status, 0) > STATUS_STRENGTH.get(r.status, 0)
                    n_stale += not r.active
                disclosed = any(not policy.allows(q.requester, by_id[rid].category, "read")
                                for rid in ans.disclosed_records)
                decision_class = "answer" if ans.substantive else ans.decision
                out.append(dict(
                    condition=cond, question_id=q.question_id, participant_id=pid, stratum=q.stratum,
                    ideal=q.ideal, decision=ans.decision, substantive=ans.substantive,
                    appropriate=decision_class == q.ideal or (q.ideal == "refuse" and ans.decision == "abstain"),
                    claims_released=len(ans.claims), claims_supported=n_sup, fabricated=n_fab,
                    overstated=n_over, stale_used=n_stale, wrong_event=n_wrong, consent_violation=disclosed,
                    s_min=ans.s_min, answer_text=ans.text,
                ))
    return pd.DataFrame(out)
