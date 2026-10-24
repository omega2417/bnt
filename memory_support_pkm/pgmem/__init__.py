"""pgmem — provenance-governed agentic memory support.

Reference implementation of the conceptual framework in
D. Prokopovych-Tkachenko, "Provenance-governed agentic AI for personal
knowledge and memory support: a conceptual framework".
"""
from .assistance import adapt_start_level, gate, next_level
from .governance import ActionQueue, PolicyEngine, QueuedAction
from .model import Episode, EpisodeState, EvidenceStatus, PersonalEventBase, Record
from .recall import Answer, Claim, GroundedRecall, NaiveRAG, Question, ReminderOnly, release, support_score

__version__ = "1.0.0"
__all__ = [
    "ActionQueue", "Answer", "Claim", "Episode", "EpisodeState", "EvidenceStatus", "GroundedRecall",
    "NaiveRAG", "PersonalEventBase", "PolicyEngine", "Question", "QueuedAction", "Record", "ReminderOnly",
    "adapt_start_level", "gate", "next_level", "release", "support_score",
]
