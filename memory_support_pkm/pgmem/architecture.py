"""Diagrams of a deployable neural-network realisation of the framework.

The paper's architecture (Figure 1) names logical roles. These diagrams bind
each role to concrete, openly available components so the design can be
built and audited:

* ``system_architecture``   – layers, devices, models, stores, governance.
* ``neural_recall_pipeline`` – the grounded-recall data flow (Eqs. 4–5) with
  model sizes and tensor shapes; neural, rule-based and governance steps are
  visually distinct, because no neural score may override a rule gate.

Component choices are a reference bill of materials, not an endorsement;
each slot can be replaced by an equivalent (e.g. another NLI cross-encoder).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch  # noqa: E402

INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
KIND = {  # fill, edge
    "neural": ("#dbe8f8", "#2a78d6"),
    "rule": ("#eeede8", "#8a8984"),
    "gov": ("#fbefd2", "#c98500"),
    "data": ("#e9e4f8", "#6250d6"),
    "edge": ("#dcf2e9", "#1baf7a"),
    "human": ("#fde4ec", "#d55181"),
}
LEGEND = [("neural", "Neural network (pretrained model)"), ("rule", "Deterministic rule (pgmem code)"),
          ("gov", "Governance / permission check"), ("data", "Storage / connector"),
          ("edge", "On-device interaction"), ("human", "Person / trusted person")]


def _box(ax, x, y, w, h, title, body="", kind="rule", fs=8.6):
    fc, ec = KIND[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9",
                                fc=fc, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h - 0.9, title, ha="center", va="top", fontsize=fs, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h - 2.6, body, ha="center", va="top", fontsize=fs - 1.4, color=INK2, linespacing=1.3)
    return (x, y, w, h)


def _arrow(ax, p, q, color=INK2, style="-|>", lw=1.3, ls="-", text=None, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
    if text:
        ax.text((p[0] + q[0]) / 2 + 0.6, (p[1] + q[1]) / 2, text, fontsize=6.8, color=color, va="center",
                style="italic")


def _band(ax, y, h, label):
    ax.add_patch(FancyBboxPatch((1, y), 72.5, h, boxstyle="round,pad=0.2,rounding_size=1.2", fc="none",
                                ec="#d6d5cf", lw=1, ls=(0, (4, 3))))
    ax.text(-0.6, y + h / 2, label, fontsize=8.5, color=INK2, va="center", ha="center", rotation=90,
            fontweight="bold")


def system_architecture(out: Path | None = None, name: str = "arch_system.png"):
    fig, ax = plt.subplots(figsize=(17, 11.5))
    ax.set(xlim=(-1.5, 100), ylim=(0, 70))
    ax.axis("off")
    fig.patch.set_facecolor(SURFACE)
    ax.text(1, 69, "PGMem — neural-network realisation on real components", fontsize=15, fontweight="bold")
    ax.text(1, 66.9, "Logical roles of Figure 1 bound to concrete models, services and stores. "
                     "Every outgoing action passes the governance column at execution time (I1).",
            fontsize=9.5, color=INK2)

    # people
    _box(ax, 3, 58.5, 17, 5.5, "Person with memory impairment", "voice · touch · glanceable cards", "human")
    _box(ax, 55, 58.5, 18, 5.5, "Trusted person (L4 only)", "agreed scopes, e.g. missed\nsafety-critical tasks", "human")

    # interaction / edge
    _band(ax, 46, 11, "1 · INTERACTION (device)")
    _box(ax, 3, 47, 13.5, 8, "Speech in", "Silero VAD (1.8 M)\n→ Whisper large-v3-turbo\n809 M, uk/en, int8", "neural")
    _box(ax, 18, 47, 13.5, 8, "Accessible app", "Flutter UI, large targets,\nresumable tasks,\nnever reads delay as 'no'", "edge")
    _box(ax, 33, 47, 13.5, 8, "Speech out", "Piper TTS uk_UA / en_GB\n(VITS, ~20 M)\nor Coqui XTTS-v2", "neural")
    _box(ax, 48, 47, 12.5, 8, "Notifications", "FCM / APNs\nlocal alarms\n(L1–L3 prompts)", "edge")
    _box(ax, 62, 47, 11, 8, "Trusted channel", "Signal / SMS\n(Twilio API)\nqueued only", "edge")

    # agentic
    _band(ax, 21.5, 23.5, "2 · AGENTIC (local inference server)")
    _box(ax, 3, 35.5, 70, 8, "Coordinator — LangGraph state machine (local server, 8–16 GB GPU or Apple silicon)",
         "goal → plan → permission check → execute → observe → adapt (Fig. 2a) · episode states "
         "pending/active/completed/postponed/declined/unknown (I3)\nconflict resolution between prompts · "
         "idempotency keys for replay (I4)", "rule", fs=9.2)
    _box(ax, 3, 23, 13, 11, "Interaction role", "Llama-3.1-8B-Instruct\nQ4_K_M via llama.cpp\n/ vLLM; plain-language\n"
                                              "dialogue, comprehension\nchecks", "neural")
    _box(ax, 17.5, 23, 13, 11, "Memory role", "BGE-M3 encoder (568 M,\n1024-d dense + sparse)\n→ BGE-reranker-v2-m3\n"
                                             "(cross-encoder, 568 M)", "neural")
    _box(ax, 32, 23, 13, 11, "Verification role", "claim decomposer (LLM,\nJSON schema) → mDeBERTa\n-v3-base-XNLI (278 M)\n"
                                                  "ent(a_j, r) → S(a_j) (Eq. 4)", "neural")
    _box(ax, 46.5, 23, 13, 11, "Assistance role", "pgmem.assistance\nEq. 2: L_{k+1} gate G_k\nEq. 3: start-level\n"
                                                  "adaptation (m, L_min)", "rule")
    _box(ax, 61, 23, 12, 11, "Release & monitor", "pgmem.recall.release\nθ_low / θ_high (Eq. 5)\nTSR, FAR, F_ext, C\n"
                                                    "(Eqs. 6–7)", "rule")

    # data
    _band(ax, 2, 18, "3 · DATA")
    _box(ax, 3, 9.5, 24, 8.5, "Personal event base", "PostgreSQL 16 + pgvector\nr_i = (c, t, s, κ, σ, v, e) · versions "
                                                     "·\nPROV-O lineage · retention covers\nembeddings, caches, backups",
         "data")
    _box(ax, 29, 9.5, 21, 8.5, "Ingestion", "MQTT (Mosquitto) → normaliser\n→ evidence typing:\nplan / self_report / "
                                            "observation /\ninference / disputed", "rule")
    _box(ax, 52, 9.5, 21, 8.5, "Connectors (opt-in)", "CalDAV / Google Calendar API\nAndroid CallLog · Health Connect\n"
                                                      "/ HealthKit · BLE smart pill box\nvia Home Assistant", "data")
    _box(ax, 3, 3, 47, 5, "Audit log — append-only, hash-chained", "every prompt, action, record change and "
                                                                   "deletion event (content never retained)", "data")

    # governance column
    ax.add_patch(FancyBboxPatch((76, 3), 22, 61, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=KIND["gov"][0], ec=KIND["gov"][1], lw=1.8))
    ax.text(87, 63, "GOVERNANCE", ha="center", va="top", fontsize=11, fontweight="bold")
    items = [("Policy engine", "Open Policy Agent (Rego)\n⇄ pgmem.PolicyEngine\nscopes = (recipient,\ncategory, action)"),
             ("Consent manager", "revisable scopes · periodic\nreminders of what is shared\nsupported decision-making"),
             ("Dispatch-time check (I1)", "ActionQueue.dispatch():\nre-evaluate permission\nimmediately before send"),
             ("Invalidation (I4)", "on correct / dispute / delete:\ndrop cached answers,\nsummaries, queued actions"),
             ("Escalation rules", "L4 only under agreed rule\n+ current permission"),
             ("Data minimisation", "on-device by default;\nno raw audio leaves device;\nGDPR Art. 9 · EU AI Act")]
    y = 59.5
    for t, b in items:
        _box(ax, 77.5, y - 8.2, 19, 8, t, b, "gov", fs=8.4)
        y -= 9.1

    # arrows
    _arrow(ax, (11, 58.5), (10, 55.3))
    _arrow(ax, (12, 58.5), (24, 55.3))
    _arrow(ax, (39.5, 47), (39.5, 43.8), style="<|-")
    _arrow(ax, (10, 47), (10, 43.8))
    _arrow(ax, (25, 47), (25, 43.8), style="<|-|>")
    _arrow(ax, (54, 47), (54, 43.8), style="<|-")
    _arrow(ax, (67, 47), (67, 43.8), style="<|-", color="#c98500", text="after I1 check")
    _arrow(ax, (67, 55), (64, 58.5), color="#d55181")
    _arrow(ax, (38, 35.5), (38, 34.2), style="<|-|>")
    for x in (9.5, 24, 52.5, 67):
        _arrow(ax, (x, 35.5), (x, 34.2), style="<|-|>")
    _arrow(ax, (24, 23), (15, 18.2), style="<|-", text="top-k, permission-filtered")
    _arrow(ax, (38.5, 23), (20, 18.2), style="<|-", text="record versions")
    _arrow(ax, (52, 13.75), (50, 13.75), style="-|>")
    _arrow(ax, (29, 13.75), (27, 13.75), style="-|>")
    for yy in (39.5, 28.5, 13.5):
        _arrow(ax, (76, yy), (73.6, yy), color="#c98500", style="<|-|>", lw=1.6)
    _arrow(ax, (76, 5.5), (50.3, 5.5), color="#c98500", style="-|>", text="audit events")

    ax.legend(handles=[Patch(fc=KIND[k][0], ec=KIND[k][1], label=l) for k, l in LEGEND], loc="lower center",
              bbox_to_anchor=(0.5, -0.04), ncol=6, fontsize=8.5, frameon=False)
    fig.tight_layout()
    if out is not None:
        fig.savefig(Path(out) / name, bbox_inches="tight", facecolor=SURFACE, dpi=170)
    return fig


def neural_recall_pipeline(out: Path | None = None, name: str = "arch_recall_pipeline.png"):
    fig, ax = plt.subplots(figsize=(17, 8.0))
    ax.set(xlim=(0, 100), ylim=(4, 52))
    ax.axis("off")
    fig.patch.set_facecolor(SURFACE)
    ax.text(1, 51, "Grounded recall as a neural pipeline (Section 4.4, Eqs. 4–5)", fontsize=15, fontweight="bold")
    ax.text(1, 48.8, "Neural models propose; rule gates dispose. A high neural score can never override a failed "
                     "permission, conflict, identity or freshness gate.", fontsize=9.5, color=INK2)

    w, h, y1, y2, y3 = 13.2, 11, 33, 17, 5
    top = [
        ("1. Audio → text", "16 kHz PCM → log-Mel\n128×3000 → Whisper enc.\n(32 layers, d=1280)\n→ dec. → tokens",
         "neural"),
        ("2. Query intent", "zero-shot NLI (mDeBERTa)\nlabels: scheduled /\noccurred / content\n→ claim kind of q",
         "neural"),
        ("3. Permission filter", "SQL WHERE scope ∋\nrequester AND category\nallowed (I1) — before\nretrieval", "gov"),
        ("4. Dense retrieval", "e5 / BGE-M3 encoder\nq, r → 384–1024-d\nL2-normalised\ncosine top-k (pgvector)",
         "neural"),
        ("5. Rerank", "cross-encoder\n[CLS] q [SEP] r\n→ relevance logit\nkeep k' ≤ 5", "neural"),
        ("6. Rule gates", "∅ → abstain\ndisputed → clarify\n>1 event identity → clarify\nsuperseded v → skip (I4)",
         "rule"),
    ]
    bottom = [
        ("7. Draft (LLM)", "Llama-3.1-8B-Instruct\nprompt = typed records\n+ evidence status;\nno free recollection",
         "neural"),
        ("8. Claim split", "atomic claims a_1..a_m\n(JSON schema:\nsubject, kind, value,\nasserted_status)", "neural"),
        ("9. Evidence-type check", "SUPPORTS[status]:\nplan ⊬ attended,\nself-report ⊬ observed\n(I2)", "rule"),
        ("10. NLI support", "mDeBERTa-v3-base-XNLI\n(278 M) softmax over\n{entail, neutral, contra}\nS(a_j)=max ent·κ_r (Eq. 4)",
         "neural"),
        ("11. Release rule", "S_min ≥ θ_high: answer+source\nθ_low ≤ S_min: uncertain\n< θ_low: abstain (Eq. 5)\n"
                           "θ calibrated on dev split", "rule"),
        ("12. Re-check & speak", "permission re-checked\nat release (I1) → TTS\n(Piper / XTTS) + source\n"
                               "date, evidence type", "gov"),
    ]
    xs = [1 + i * (w + 3.3) for i in range(6)]
    for x, (t, b, k) in zip(xs, top):
        _box(ax, x, y1, w, h, t, b, k, fs=9)
    for x, (t, b, k) in zip(xs[::-1], bottom):
        _box(ax, x, y2, w, h, t, b, k, fs=9)
    for i in range(5):
        _arrow(ax, (xs[i] + w + 0.3, y1 + h / 2), (xs[i + 1] - 0.3, y1 + h / 2), lw=1.6)
        _arrow(ax, (xs[i + 1] - 0.3, y2 + h / 2), (xs[i] + w + 0.3, y2 + h / 2), lw=1.6)
    _arrow(ax, (xs[5] + w / 2, y1 - 0.3), (xs[5] + w / 2, y2 + h + 0.3), lw=1.6, text="records pass")
    _arrow(ax, (xs[5] + w + 0.4, y1 + 3), (99, 31), color="#e34948", text="")
    ax.text(97.5, 30, "clarify /\nabstain", fontsize=8, color="#e34948", ha="center", va="top")

    # outcome strip: what is NOT neural
    notes = [("Training / calibration", "NLI & reranker used zero-shot; θ_low, θ_high fitted on development histories,\n"
                                         "reported on held-out ones (pgmem.stats.calibrate_threshold)."),
             ("Failure modes kept visible", "retrieval of the wrong event (wrong_event), noisy entailment,\n"
                                             "ASR errors — measured by F_ext and coverage, never hidden."),
             ("Runs in this notebook", "Steps 2 (zero-shot intent), 4 (e5-small) and 10 (mDeBERTa-XNLI) run live\n"
                                       "in pgmem.neural (with an offline lexical fallback).")]
    for i, (t, b) in enumerate(notes):
        x = 1 + i * 33.2
        _box(ax, x, y3, 31.8, 7.5, t, b, "rule" if i < 2 else "neural", fs=9)

    ax.legend(handles=[Patch(fc=KIND[k][0], ec=KIND[k][1], label=l) for k, l in LEGEND[:3]], loc="upper right",
              bbox_to_anchor=(1.0, 0.985), ncol=3, fontsize=8.5, frameon=False)
    fig.tight_layout()
    if out is not None:
        fig.savefig(Path(out) / name, bbox_inches="tight", facecolor=SURFACE, dpi=170)
    return fig
