"""Dataset metadata (Frictionless Data Package) and validation.

The same descriptor documents the synthetic data and lets a team check
that a real, ethically approved dataset with the same structure can be
analysed by this code without changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

F = lambda name, type_, desc, **c: {"name": name, "type": type_, "description": desc,
                                     **({"constraints": c} if c else {})}

RESOURCES = {
    "participants": ("Cohort participants and memory-related metadata (one row = one person)", [
        F("participant_id", "string", "Pseudonymised identifier", required=True, unique=True, pattern=r"P\d{3}"),
        F("age", "integer", "Age, years", minimum=18, maximum=110),
        F("age_band", "string", "Age band", enum=["<50", "50-64", "65-74", "75-84", "85+"]),
        F("sex", "string", "Sex", enum=["F", "M"]),
        F("diagnosis", "string", "MCI — mild cognitive impairment; mild_dementia — mild dementia; ABI — acquired brain injury",
          enum=["MCI", "mild_dementia", "ABI"]),
        F("cdr_global", "number", "Clinical Dementia Rating, global score (empty for ABI)", minimum=0, maximum=3),
        F("moca", "integer", "Montreal Cognitive Assessment, education-adjusted (0–30)", minimum=0, maximum=30),
        F("education_years", "integer", "Years of education", minimum=0, maximum=30),
        F("prmq_prospective", "integer", "PRMQ prospective subscale (8–40, higher = more frequent failures)", minimum=8, maximum=40),
        F("prmq_retrospective", "integer", "PRMQ retrospective subscale (8–40)", minimum=8, maximum=40),
        F("months_since_diagnosis", "integer", "Months since diagnosis", minimum=0),
        F("lives_alone", "boolean", "Lives alone"),
        F("has_trusted_person", "boolean", "Has an agreed trusted person (R8)"),
        F("trusted_relation", "string", "Relation of the trusted person"),
        F("device", "string", "Device", enum=["smartphone", "tablet", "both"]),
        F("digital_literacy", "integer", "Self-rated digital literacy (1–5)", minimum=1, maximum=5),
        F("uses_voice", "boolean", "Uses voice interaction (R6)"),
        F("sensors_connected", "boolean", "Sensors connected (pill box, step counter)"),
        F("call_log_connected", "boolean", "Call log connected"),
        F("language", "string", "Interface language", enum=["uk", "en"]),
        F("agrees_to_level_reduction", "boolean", "Agrees to lowering the starting assistance level (Eq. 3)"),
        F("ability_latent", "number", "SIMULATION ONLY: latent ability from which responses are generated"),
    ]),
    "episodes": ("Scheduled task episodes (routines, R1–R4)", [
        F("episode_id", "string", "Episode identifier", required=True, unique=True),
        F("participant_id", "string", "Reference to participants", required=True),
        F("day", "integer", "Observation day (0–27)", minimum=0),
        F("task_type", "string", "Task type",
          enum=["medication_morning", "daily_walk", "appointment_prep", "bill_payment", "call_family"]),
        F("category", "string", "Data category used for consent"),
        F("safety_critical", "boolean", "Safety-critical task"),
        F("sensorable", "boolean", "Completion can be detected by a sensor"),
        F("scheduled", "datetime", "Scheduled time (ISO 8601)"),
    ]),
    "records": ("Personal event base: records r_i = (c, t, s, κ, σ, v, e), Equation (1)", [
        F("record_id", "string", "Record identifier", required=True, unique=True),
        F("person_id", "string", "Whose record this is", required=True),
        F("subject", "string", "Event identity"),
        F("content", "string", "c_i — content"),
        F("time", "datetime", "t_i — time"),
        F("source", "string", "s_i — source/provenance (calendar, user_voice, sensor, call_log, carer_entry)"),
        F("kappa", "number", "κ_i — confidence indicator (not a probability)", minimum=0, maximum=1),
        F("scope", "string", "σ_i — permitted recipients (comma-separated)"),
        F("version", "integer", "v_i — version", minimum=1),
        F("status", "string", "e_i — evidence status",
          enum=["plan", "self_report", "observation", "inference", "disputed"]),
        F("category", "string", "Data category"),
        F("kind", "string", "What the record speaks to: scheduled / occurred / content", enum=["scheduled", "occurred", "content"]),
        F("value", "string", "Normalised claim value"),
        F("supersedes", "string", "Previous version superseded by this record"),
        F("active", "boolean", "Current version"),
        F("disputed", "boolean", "Marked as disputed"),
    ]),
    "questions": ("Questions to the assistant about the past, with evaluation strata", [
        F("question_id", "string", "Identifier", required=True, unique=True),
        F("person_id", "string", "Whom the question is about"),
        F("stratum", "string", "Stratum", enum=["answerable_plan", "attendance", "self_report", "unanswerable",
                                                 "answerable_observation", "contradictory", "stale",
                                                 "answerable_note", "consent_restricted"]),
        F("requester", "string", "Who asks (the person or trusted:<id>)"),
        F("subject", "string", "Event"),
        F("kind", "string", "Claim kind"),
        F("category", "string", "Data category"),
        F("ideal", "string", "Reference (ideal) behaviour", enum=["answer", "abstain", "clarify", "refuse"]),
        F("text", "string", "Question text"),
    ]),
    "reference_history": ("Independent reference history (ground truth) for blinded claim scoring", [
        F("person_id", "string", "Person"),
        F("subject", "string", "Event"),
        F("kind", "string", "scheduled / occurred / reported / content"),
        F("value", "string", "True value"),
    ]),
}


def descriptor(seed: int, n: int, days: int) -> dict:
    return {
        "name": "pgmem-synthetic-memory-support",
        "title": "Synthetic dataset for evaluating a provenance-governed memory assistant",
        "version": "1.0.0",
        "licenses": [{"name": "CC-BY-4.0"}],
        "description": (
            "Fully synthetic data generated from the Prokopovych-Tkachenko framework 'Provenance-governed agentic AI "
            "for personal knowledge and memory support' (stage 1 of the evaluation protocol). No record "
            "corresponds to a real person; distributions are design assumptions, not empirical estimates."),
        "synthetic": True,
        "generator": {"package": "pgmem", "seed": seed, "participants": n, "days": days},
        "resources": [
            {"name": k, "path": f"{k}.csv", "format": "csv", "description": d, "schema": {"fields": f}}
            for k, (d, f) in RESOURCES.items()
        ],
    }


def write_descriptor(path: Path, seed: int, n: int, days: int) -> None:
    path.write_text(json.dumps(descriptor(seed, n, days), ensure_ascii=False, indent=2), encoding="utf-8")


def validate(data_dir: Path) -> list[str]:
    """Check every CSV against datapackage.json; returns a list of problems."""
    desc = json.loads((Path(data_dir) / "datapackage.json").read_text(encoding="utf-8"))
    problems = []
    for res in desc["resources"]:
        df = pd.read_csv(Path(data_dir) / res["path"], keep_default_na=False, na_values=[""])
        for f in res["schema"]["fields"]:
            name, c = f["name"], f.get("constraints", {})
            if name not in df.columns:
                problems.append(f"{res['name']}: missing column {name}")
                continue
            col = df[name]
            if c.get("required") and col.isna().any():
                problems.append(f"{res['name']}.{name}: empty values")
            if c.get("unique") and col.duplicated().any():
                problems.append(f"{res['name']}.{name}: duplicates")
            if "enum" in c and not col.dropna().astype(str).isin(c["enum"]).all():
                problems.append(f"{res['name']}.{name}: values outside enum")
            num = pd.to_numeric(col, errors="coerce")
            if "minimum" in c and (num < c["minimum"]).any():
                problems.append(f"{res['name']}.{name}: < {c['minimum']}")
            if "maximum" in c and (num > c["maximum"]).any():
                problems.append(f"{res['name']}.{name}: > {c['maximum']}")
            if "pattern" in c and not col.astype(str).str.fullmatch(c["pattern"]).all():
                problems.append(f"{res['name']}.{name}: does not match pattern")
    return problems
