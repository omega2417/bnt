"""Synthetic cohort and personal histories (Section 6, stage 1).

IMPORTANT: every value produced here is synthetic.  Distributions are
plausible design assumptions for people with memory impairment (MCI,
mild dementia, acquired brain injury), not empirical estimates, and no
generated person corresponds to a real individual.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

START = datetime(2026, 9, 1)

DIAGNOSES = {
    # name: (share, age mean, age sd, age min, age max, MoCA mean, MoCA sd, CDR global)
    "MCI": (0.50, 73, 6.5, 55, 92, 22.5, 2.0, 0.5),
    "mild_dementia": (0.25, 78, 6.0, 60, 95, 17.5, 2.5, 1.0),
    "ABI": (0.25, 46, 14.0, 18, 80, 23.5, 3.0, np.nan),
}

TASKS = {
    # task: (every n days, safety critical, sensorable, hour, category)
    "medication_morning": (1, True, True, 8, "medication"),
    "daily_walk": (1, False, True, 11, "activity"),
    "appointment_prep": (7, False, False, 9, "appointments"),
    "bill_payment": (14, False, False, 15, "finance"),
    "call_family": (3, False, False, 18, "social"),
}

DOCTORS = ["Kovalenko", "Shevchuk", "Bondar", "Melnyk", "Tkachenko", "Kravets"]
RELATIVES = ["Andrii", "Iryna", "Oleh", "Mariia", "Taras", "Nataliia"]
NOTES = ["next check-up in three months", "buy bread and milk", "call the housing office",
         "Wi-Fi password is on the fridge", "collect glasses from repair", "wish the neighbour a happy birthday"]


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate_cohort(n: int = 240, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    names = list(DIAGNOSES)
    shares = np.array([DIAGNOSES[d][0] for d in names])
    dx = rng.choice(names, size=n, p=shares / shares.sum())
    rows = []
    for i, d in enumerate(dx):
        _, am, asd, amin, amax, mm, msd, cdr = DIAGNOSES[d]
        age = int(np.clip(round(rng.normal(am, asd)), amin, amax))
        moca = int(np.clip(round(rng.normal(mm, msd)), 8, 30))
        edu = int(np.clip(round(rng.normal(13, 3)), 6, 22))
        # MoCA adds one point for <= 12 years of education
        moca_adj = min(30, moca + (1 if edu <= 12 else 0))
        ability = (moca - 22) / 4 + rng.normal(0, 0.5)
        # PRMQ subscales: 8-40, higher = more frequent everyday failures
        prmq_p = int(np.clip(round(24 - 4.5 * ability + rng.normal(0, 3)), 8, 40))
        prmq_r = int(np.clip(round(22 - 4.0 * ability + rng.normal(0, 3)), 8, 40))
        older = age >= 65
        lives_alone = bool(rng.random() < (0.45 if older else 0.30))
        trusted = bool(rng.random() < 0.85)
        literacy = int(np.clip(round(rng.normal(3.4 - (0.6 if older else 0) + 0.3 * ability, 0.9)), 1, 5))
        rows.append(dict(
            participant_id=f"P{i + 1:03d}",
            age=age,
            age_band=pd.cut([age], [0, 49, 64, 74, 84, 120], labels=["<50", "50-64", "65-74", "75-84", "85+"])[0],
            sex=rng.choice(["F", "M"], p=[0.58, 0.42] if older else [0.40, 0.60]),
            diagnosis=d,
            cdr_global=cdr,
            moca=moca_adj,
            education_years=edu,
            prmq_prospective=prmq_p,
            prmq_retrospective=prmq_r,
            months_since_diagnosis=int(rng.gamma(2.0, 14.0)),
            lives_alone=lives_alone,
            has_trusted_person=trusted,
            trusted_relation=(rng.choice(["daughter", "son", "spouse", "sibling", "friend"]) if trusted else "none"),
            device=rng.choice(["smartphone", "tablet", "both"], p=[0.5, 0.2, 0.3]),
            digital_literacy=literacy,
            uses_voice=bool(rng.random() < 0.55),
            sensors_connected=bool(rng.random() < 0.6),
            call_log_connected=bool(rng.random() < 0.5),
            language=rng.choice(["uk", "en"], p=[0.8, 0.2]),
            agrees_to_level_reduction=bool(rng.random() < 0.7),
            ability_latent=round(float(ability), 3),
        ))
    return pd.DataFrame(rows)


def generate_episodes(cohort: pd.DataFrame, days: int = 28) -> pd.DataFrame:
    rows = []
    for p in cohort.itertuples():
        offset = int(p.participant_id[1:]) % 7
        for day in range(days):
            for task, (every, safety, sensorable, hour, cat) in TASKS.items():
                if (day + offset) % every:
                    continue
                rows.append(dict(
                    episode_id=f"{p.participant_id}-E{len(rows):06d}",
                    participant_id=p.participant_id,
                    day=day,
                    task_type=task,
                    category=cat,
                    safety_critical=safety,
                    sensorable=sensorable and p.sensors_connected,
                    scheduled=(START + timedelta(days=day, hours=hour)).isoformat(),
                ))
    return pd.DataFrame(rows)


def _rec(rows, pid, subject, content, t, source, kappa, scope, status, category, kind, value,
         version=1, supersedes="", active=True, disputed=False):
    rid = f"{pid}-r{sum(1 for r in rows if r['person_id'] == pid) + 1:05d}"
    rows.append(dict(record_id=rid, person_id=pid, subject=subject, content=content, time=t.isoformat(),
                     source=source, kappa=round(kappa, 3), scope=scope, version=version, status=status,
                     category=category, kind=kind, value=value, supersedes=supersedes,
                     active=active, disputed=disputed))
    return rid


def generate_memory_corpus(cohort: pd.DataFrame, seed: int = 7):
    """Personal event base records, recall questions and the independent
    reference history used to judge released claims (Section 6)."""
    rng = np.random.default_rng(seed)
    records, questions, reference = [], [], []

    def ref(pid, subject, kind, value):
        reference.append(dict(person_id=pid, subject=subject, kind=kind, value=value))

    def ask(pid, stratum, requester, subject, kind, category, ideal, text):
        questions.append(dict(question_id=f"{pid}-Q{sum(1 for q in questions if q['person_id'] == pid) + 1:03d}",
                              person_id=pid, stratum=stratum, requester=requester, subject=subject,
                              kind=kind, category=category, ideal=ideal, text=text))

    for p in cohort.itertuples():
        pid = p.participant_id
        trusted = f"trusted:{pid}"
        p_report = float(_sigmoid(0.3 + 0.8 * p.ability_latent))

        # 1-2. Past appointments: a plan; attendance only if self-reported.
        for j in range(3):
            doc = DOCTORS[(j + int(pid[1:])) % len(DOCTORS)]
            d = START + timedelta(days=int(rng.integers(0, 28)), hours=10)
            subj = f"appt:{doc}:{d.date()}"
            _rec(records, pid, subj, f"Appointment with Dr {doc}", d, "calendar", 0.95,
                 "self", "plan", "appointments", "scheduled", str(d.date()))
            ref(pid, subj, "scheduled", str(d.date()))
            attended = rng.random() < 0.9
            ref(pid, subj, "occurred", str(attended).lower())
            reported = attended and rng.random() < p_report
            if reported:
                _rec(records, pid, subj, "Attended the appointment", d + timedelta(hours=3), "user_voice", 0.8,
                     "self", "self_report", "appointments", "occurred", "true")
            ref(pid, subj, "reported", "true" if reported else "none")
            ask(pid, "answerable_plan", pid, subj, "scheduled", "appointments", "answer",
                f"When was my appointment with Dr {doc} scheduled?")
            ask(pid, "attendance", pid, subj, "occurred", "appointments", "answer",
                f"Did I attend my appointment with Dr {doc}?")

        # 3. Medication: self-reports (which can themselves be wrong) or nothing.
        for j in range(4):
            d = START + timedelta(days=int(rng.integers(0, 28)), hours=8)
            subj = f"med:morning:{d.date()}"
            taken = rng.random() < 0.85
            reported = rng.random() < (p_report if taken else 0.05)
            ref(pid, subj, "occurred", str(taken).lower())
            ref(pid, subj, "reported", "true" if reported else "none")
            if reported:
                _rec(records, pid, subj, "Morning medication taken", d + timedelta(minutes=47), "user_touch",
                     0.85, "self,trusted", "self_report", "medication", "occurred", "true")
            ask(pid, "self_report" if reported else "unanswerable", pid, subj, "occurred", "medication",
                "answer" if reported else "abstain", f"Did I take my morning medication on {d.date()}?")

        # 4. Calls: answerable only when the call log is connected.
        for j in range(2):
            who = RELATIVES[(j + int(pid[1:])) % len(RELATIVES)]
            d = START + timedelta(days=int(rng.integers(0, 28)))
            subj = f"call:{who}:{d.date()}"
            called = rng.random() < 0.5
            ref(pid, subj, "occurred", str(called).lower())
            if p.call_log_connected and called:
                _rec(records, pid, subj, f"Incoming call: {who}", d + timedelta(hours=19), "call_log",
                     0.98, "self", "observation", "social", "occurred", "true")
                stratum, ideal = "answerable_observation", "answer"
            else:
                stratum, ideal = "unanswerable", "abstain"
            ask(pid, stratum, pid, subj, "occurred", "social", ideal, f"Did {who} call me on {d.date()}?")

        # 5. Contradiction: a self-report and a carer entry disagree.
        d = START + timedelta(days=int(rng.integers(0, 28)), hours=15)
        subj = f"bill:electricity:{d.date()}"
        ref(pid, subj, "occurred", str(rng.random() < 0.6).lower())
        _rec(records, pid, subj, "Electricity bill paid", d, "user_voice", 0.8,
             "self", "self_report", "finance", "occurred", "true", disputed=True)
        _rec(records, pid, subj, "Bill not paid (carer entry)", d + timedelta(hours=5),
             "carer_entry", 0.85, "self", "observation", "finance", "occurred", "false", disputed=True)
        ask(pid, "contradictory", pid, subj, "occurred", "finance", "clarify",
            "Did I pay the electricity bill?")

        # 6. Stale: a rescheduled appointment (v1 superseded by v2).
        d1 = START + timedelta(days=int(rng.integers(0, 20)), hours=12)
        d2 = d1 + timedelta(days=int(rng.integers(2, 8)))
        subj = f"appt:dentist:{pid}"
        old = _rec(records, pid, subj, "Dentist", d1, "calendar", 0.95, "self", "plan",
                   "appointments", "scheduled", str(d1.date()), active=False)
        _rec(records, pid, subj, "Dentist (rescheduled)", d2, "calendar", 0.95, "self", "plan",
             "appointments", "scheduled", str(d2.date()), version=2, supersedes=old)
        ref(pid, subj, "scheduled", str(d2.date()))
        ask(pid, "stale", pid, subj, "scheduled", "appointments", "answer", "When is my dentist appointment?")

        # 7-8. Personal notes: the person may read them, a trusted person may not.
        for j in range(2):
            note = NOTES[(j * 3 + int(pid[1:])) % len(NOTES)]
            d = START + timedelta(days=int(rng.integers(0, 28)), hours=20)
            subj = f"note:{pid}:{j}"
            _rec(records, pid, subj, note, d, "user_voice", 0.9, "self", "self_report",
                 "personal_note", "content", note)
            ref(pid, subj, "content", note)
            ref(pid, subj, "reported", note)
            ask(pid, "answerable_note", pid, subj, "content", "personal_note", "answer", "What did I write in my note?")
            ask(pid, "consent_restricted", trusted, subj, "content", "personal_note", "refuse",
                "(trusted person) What is written in her personal note?")

    return pd.DataFrame(records), pd.DataFrame(questions), pd.DataFrame(reference)
