"""Показники з плану оцінювання публікації (табл. 6), які можна обчислити з журналу.

Показники описують якість інформації та простежуваність аналітичної роботи.
Якість самого рішення вони не вимірюють: її оцінює окрема експертна група.
"""
from __future__ import annotations


def recall_precision(retrieved: list[str], reference: list[str], relevant: list[str] | None = None) -> dict:
    """Повнота - частка еталонних джерел серед знайдених; точність - частка релевантних серед знайдених."""
    got, ref = set(retrieved), set(reference)
    rel = set(relevant) if relevant is not None else ref
    return {"retrieved": len(got), "reference": len(ref),
            "recall": len(got & ref) / len(ref) if ref else None,
            "precision": len(got & rel) / len(got) if got else None}


def case_indicators(case) -> dict:
    st = case.state()
    brief = st["signed"] or (st["drafts"][-1] if st["drafts"] else None)
    in_brief = unverified = 0
    if brief:
        c = brief["payload"]["content"]
        in_brief = len(c["context"]) + sum(len(o["supporting"]) + len(o["dissenting"]) for o in c["options"])
        unverified = len(c["unverified"])
    verdicts = [v["payload"] for v in st["verifications"].values()]
    agent_v = [v for v in verdicts if v["proposed_by"] == "agent"]
    count = lambda rows, verdict: sum(1 for v in rows if v["verdict"] == verdict)
    total_claims = in_brief + unverified
    audits = [a["payload"] for a in st["audits"] if a["payload"].get("blind_checked")]
    blind = None
    if audits:
        blind = sum(a["blind_unsupported"] or 0 for a in audits) / sum(a["blind_checked"] for a in audits)
    retrieved = sorted({k for q in st["queries"] for k in q["payload"]["retrieved"]})
    return {
        "zone": st["zone"],
        "sources_retrieved": len(st["sources"]),
        "sources_unusable": sum(1 for s in st["sources"].values() if s["prov"] and not s["prov"]["payload"]["usable"]),
        "retrieved_keys": retrieved,
        "claims_in_brief": total_claims,
        # частка тверджень довідки, пов'язаних із перевіреним фрагментом повного тексту
        "traceability_rate": in_brief / total_claims if total_claims else None,
        "g1_checked": len(verdicts),
        "g1_accept": count(verdicts, "accept"), "g1_modify": count(verdicts, "modify"),
        "g1_reject": count(verdicts, "reject"),
        # частка пропозицій агента, які аналітик відхилив або змінив (патерни перегляду, P5)
        "agent_override_rate": (count(agent_v, "reject") + count(agent_v, "modify")) / len(agent_v) if agent_v else None,
        "agent_reject_rate": count(agent_v, "reject") / len(agent_v) if agent_v else None,
        # частка непідтверджених тверджень за сліпим оглядом наглядового форуму (якщо проводився)
        "unsupported_claim_rate_blind": blind,
        "escalations": max(0, len(st["zone_events"]) - 1),
        "triggers": st["triggers"],
        "reused_claims": sum(1 for c in st["claims"].values() if c["reused"]),
        "transfers": len(st["transfers"]),
        "reconstructable": case.reconstruct()["reconstructable"] if st["decision"] else None,
        "record_entries": len(case.record),
        "integrity_ok": not case.record.verify(),
    }
