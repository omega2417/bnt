"""Real neural components for the grounded-recall pipeline.

* ``NLIScorer``      – multilingual NLI cross-encoder that estimates
  ent(a_j, r) in Equation (4) (default: mDeBERTa-v3-base-XNLI, 278 M).
* ``DenseRetriever`` – sentence-embedding retriever (default:
  multilingual-e5-small, 118 M, 384-d) over permission-filtered records.
* ``IntentClassifier`` – zero-shot claim-kind detection with the same NLI model.
* ``NeuralRecall``   – free-text question -> intent -> retrieval ->
  ``GroundedRecall`` gates -> NLI support -> release rule.

Every class degrades to a transparent lexical fallback when ``transformers``
/ ``sentence-transformers`` or the model weights are unavailable (offline
runs, CI), and reports which backend it used. The rule gates and the
evidence-type check stay deterministic in both cases: a neural score is an
input to Eq. (4), never a substitute for I1–I4.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

import numpy as np

from .model import SUPPORTS, Record
from .recall import Answer, Claim, GroundedRecall, Question

NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
EMB_MODEL = "intfloat/multilingual-e5-small"

_TOKEN = re.compile(r"[\w\-]+", re.UNICODE)
_STOP = {"the", "a", "an", "of", "to", "on", "in", "at", "for", "was", "is", "my", "i", "did", "do", "me",
         "that", "this", "with", "by", "and", "or", "it", "have", "has", "been", "be"}


def _tokens(s: str) -> set[str]:
    return {t for t in _TOKEN.findall(s.lower()) if t not in _STOP}


def _device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ------------------------------------------------------------------- NLI
class NLIScorer:
    """P(entailment | premise, hypothesis) from an NLI cross-encoder."""

    def __init__(self, model_name: str = NLI_MODEL, use_model: bool = True, batch_size: int = 16):
        self.model_name, self.batch_size = model_name, batch_size
        self.backend = "lexical-fallback"
        self._cache: dict[tuple[str, str], float] = {}
        if not use_model:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self._torch = torch
            self.tok = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(_device()).eval()
            labels = {v.lower(): int(k) for k, v in self.model.config.id2label.items()}
            self.entail_id = next(i for name, i in labels.items() if name.startswith("entail"))
            self.backend = model_name
        except Exception as exc:  # offline, no weights, no torch ...
            warnings.warn(f"NLI model unavailable ({type(exc).__name__}: {exc}); using lexical fallback")

    def entail(self, premises: Sequence[str], hypotheses: Sequence[str]) -> np.ndarray:
        pairs = list(zip(premises, hypotheses))
        todo = [p for p in dict.fromkeys(pairs) if p not in self._cache]
        if todo:
            scores = self._model_scores(todo) if self.backend != "lexical-fallback" else \
                [self._lexical(p, h) for p, h in todo]
            self._cache.update(zip(todo, map(float, scores)))
        return np.array([self._cache[p] for p in pairs])

    def _model_scores(self, pairs):
        out = []
        for i in range(0, len(pairs), self.batch_size):
            chunk = pairs[i:i + self.batch_size]
            enc = self.tok([p for p, _ in chunk], [h for _, h in chunk], truncation=True, padding=True,
                           return_tensors="pt").to(self.model.device)
            with self._torch.no_grad():
                probs = self.model(**enc).logits.softmax(-1)[:, self.entail_id]
            out.extend(probs.cpu().numpy().tolist())
        return out

    @staticmethod
    def _lexical(premise: str, hypothesis: str) -> float:
        """Share of hypothesis content words found in the premise; a crude,
        clearly-labelled stand-in, so offline runs stay executable."""
        h, p = _tokens(hypothesis), _tokens(premise)
        return 0.0 if not h else 0.95 * len(h & p) / len(h)

    def matrix(self, premises: Sequence[str], hypotheses: Sequence[str]):
        import pandas as pd
        P = [p for p in premises for _ in hypotheses]
        H = [h for _ in premises for h in hypotheses]
        return pd.DataFrame(self.entail(P, H).reshape(len(premises), len(hypotheses)),
                            index=list(premises), columns=list(hypotheses))


# ----------------------------------------------------- verbalisation (I2)
def humanise_subject(subject: str) -> str:
    kind, *rest = subject.split(":")
    names = {"appt": "the appointment", "med": "the morning medication", "call": "the call",
             "bill": "the bill", "note": "the note"}
    rest = [r for r in rest if not r.startswith("P") or not r[1:].isdigit()]
    return " ".join([names.get(kind, kind)] + [r.replace("_", " ") for r in rest])


def verbalise_record(r: Record) -> str:
    when = r.time.strftime("%d %B %Y at %H:%M")
    lead = {"plan": f"The calendar lists: {r.content}, planned for {when}.",
            "self_report": f"The person reported on {when}: {r.content}.",
            "observation": f"The source '{r.source}' observed on {when}: {r.content}.",
            "inference": f"The assistant inferred: {r.content}.",
            "disputed": f"A disputed entry says: {r.content}."}
    return lead.get(r.status.value, r.content)


def _date(v: str) -> str:
    try:
        return datetime.fromisoformat(v).strftime("%d %B %Y")
    except ValueError:
        return v


def verbalise_claim(c: Claim, label: str | None = None) -> str:
    what = label or humanise_subject(c.subject)
    if c.kind == "scheduled":
        return f"{what} was planned for {_date(c.value)}."
    if c.kind == "occurred":
        verb = "took place" if c.value == "true" else "did not take place"
        if c.asserted_status.value == "self_report":
            return f"The person reported that {what} {verb}."
        return f"{what} {verb}."
    return f"The note says: {c.value}."


def neural_sup(scorer: NLIScorer) -> Callable[[Claim, Record], float]:
    """ent(a_j, r) for Eq. (4). The evidence-type check (I2) is applied first
    and is not learnable: a plan never supports 'it happened', however
    fluent the entailment model finds the pair."""
    def f(claim: Claim, r: Record) -> float:
        if r.status not in SUPPORTS.get(claim.asserted_status, set()):
            return 0.0
        return float(scorer.entail([verbalise_record(r)], [verbalise_claim(claim, r.content)])[0])
    return f


# -------------------------------------------------------------- retrieval
class DenseRetriever:
    """Cosine top-k over e5 embeddings ("query: " / "passage: " prefixes)."""

    def __init__(self, model_name: str = EMB_MODEL, use_model: bool = True):
        self.model_name, self.backend = model_name, "lexical-fallback"
        if use_model:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(model_name, device=_device())
                self.backend = model_name
            except Exception as exc:
                warnings.warn(f"Embedding model unavailable ({type(exc).__name__}: {exc}); using lexical fallback")

    def encode(self, texts: Sequence[str], prefix: str) -> np.ndarray:
        if self.backend != "lexical-fallback":
            return np.asarray(self.model.encode([prefix + t for t in texts], normalize_embeddings=True))
        dim = 512
        out = np.zeros((len(texts), dim))
        for i, t in enumerate(texts):
            for tok in _tokens(t):
                out[i, hash(tok) % dim] += 1.0
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)

    def scores(self, query: str, records: Sequence[Record]) -> np.ndarray:
        if not records:
            return np.zeros(0)
        q = self.encode([query], "query: ")
        d = self.encode([f"{verbalise_record(r)} ({humanise_subject(r.subject)})" for r in records], "passage: ")
        return (d @ q.T).ravel()


# ------------------------------------------------------- intent detection
INTENT_LABELS = {
    "scheduled": "This question asks when something is planned or scheduled.",
    "occurred": "This question asks whether something actually happened.",
    "content": "This question asks what a written note says.",
}


class IntentClassifier:
    def __init__(self, scorer: NLIScorer):
        self.scorer = scorer

    def __call__(self, question: str) -> tuple[str, dict[str, float]]:
        if self.scorer.backend == "lexical-fallback":
            ql = question.lower()
            kind = "content" if "note" in ql else "scheduled" if re.search(r"\bwhen\b", ql) else "occurred"
            return kind, {k: float(k == kind) for k in INTENT_LABELS}
        s = self.scorer.entail([question] * len(INTENT_LABELS), list(INTENT_LABELS.values()))
        probs = {k: float(v) for k, v in zip(INTENT_LABELS, (s / s.sum()).round(3))}
        return max(probs, key=probs.get), probs


# ------------------------------------------------------- identity check
_NOT_NAMES = {"I", "Dr", "Did", "When", "What", "Who", "Was", "Is", "Has", "Have", "Do", "Does", "My", "The"}
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def identity_ok(query: str, r: Record) -> bool:
    """Deterministic event-identity check: every proper name and ISO date in
    the question must occur in the record. Dense similarity alone happily
    matches 'Did Andrii call?' to a call from Oleh (Table 3, row 1 logic)."""
    text = f"{r.subject} {r.content} {r.value} {r.time.date()}".lower()
    names = {w for w in re.findall(r"\b[A-Z][a-z]+\b", query) if w not in _NOT_NAMES}
    return all(n.lower() in text for n in names) and all(d in text for d in _DATE.findall(query))


# --------------------------------------------------------------- pipeline
@dataclass
class NeuralTrace:
    question: str
    intent: str
    intent_probs: dict
    retrieved: list[tuple[str, float]]
    answer: Answer


class NeuralRecall:
    """Free-text recall: neural steps propose, ``GroundedRecall`` disposes."""

    def __init__(self, recall: GroundedRecall, retriever: DenseRetriever, intent: IntentClassifier,
                 top_k: int = 3, min_similarity: float | None = None, margin: float = 0.03):
        self.recall, self.retriever, self.intent = recall, retriever, intent
        if min_similarity is None:   # e5 cosines are compressed towards 1; the hashed fallback is not
            min_similarity = 0.80 if retriever.backend != "lexical-fallback" else 0.20
        self.top_k, self.min_similarity, self.margin = top_k, min_similarity, margin
        self._query = ""
        self._last: list[tuple[str, float]] = []
        recall.retriever = self._retrieve

    def _retrieve(self, q: Question, permitted: list[Record]) -> list[Record]:
        # Only permission-filtered records reach the encoder (I1); records that
        # contradict a name or date in the question never reach the gates.
        permitted = [r for r in permitted if identity_ok(self._query, r)]
        sims = self.retriever.scores(self._query, permitted)
        order = np.argsort(-sims)[: self.top_k]
        self._last = [(permitted[i].subject, float(sims[i])) for i in order]
        if not len(order) or sims[order[0]] < self.min_similarity:
            return []
        best = sims[order[0]]
        # keep every record whose similarity is within the margin of the best:
        # two different events this close trigger the identity gate (clarify).
        near = {permitted[i].subject for i in order if best - sims[i] <= self.margin}
        return [r for r in permitted if r.subject in near]

    def ask(self, text: str, person_id: str, requester: str | None = None, category: str = "*") -> NeuralTrace:
        kind, probs = self.intent(text)
        self._query = text
        self.recall._cache.clear()
        q = Question("nq", person_id, requester or person_id, subject="?", kind=kind, category=category, text=text)
        ans = self._answer(q)
        return NeuralTrace(text, kind, probs, self._last, ans)

    def _answer(self, q: Question) -> Answer:
        recs = self.recall._retrieve(q)
        subjects = {r.subject for r in recs}
        if len(subjects) == 1:
            subject = subjects.pop()
            cat = next(r.category for r in recs)
            q = Question(q.question_id, q.person_id, q.requester, subject, q.kind, cat, q.text)
            return self.recall._answer(q)
        if not recs:
            return Answer("abstain", text="I don't have any record that matches this question, so I cannot know it.")
        return Answer("clarify", text="I found records about several similar events. Which one do you mean?")
