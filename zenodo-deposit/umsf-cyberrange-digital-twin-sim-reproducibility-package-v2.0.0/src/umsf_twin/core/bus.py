"""Causal event bus.

Messages between federates are never delivered in dictionary order: they are
sorted by the stable key of specification section 6.5, and an effect scheduled
during step ``T`` can only become visible at ``T + delta_min``.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Iterator

from .clock import Phase

__all__ = ["Message", "EventBus"]


@dataclass(frozen=True)
class Message:
    time_ns: int
    phase: Phase
    source_id: str
    source_sequence: int
    event_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.time_ns, int(self.phase), self.source_id,
                self.source_sequence, self.event_id)


class EventBus:
    """Priority queue plus an append-only journal of everything delivered."""

    def __init__(self, journal_limit: int = 200_000) -> None:
        self._heap: list[tuple[tuple, int, Message]] = []
        self._counter = itertools.count()
        self._sequence: dict[str, int] = {}
        self.journal: list[Message] = []
        self.journal_limit = journal_limit
        self.dropped_journal_records = 0

    def publish(self, time_ns: int, phase: Phase, source_id: str, kind: str,
                payload: dict[str, Any] | None = None, event_id: str = "") -> Message:
        sequence = self._sequence.get(source_id, 0)
        self._sequence[source_id] = sequence + 1
        message = Message(
            time_ns=time_ns,
            phase=phase,
            source_id=source_id,
            source_sequence=sequence,
            event_id=event_id or f"{source_id}:{kind}:{sequence}",
            kind=kind,
            payload=dict(payload or {}),
        )
        heapq.heappush(self._heap, (message.key, next(self._counter), message))
        return message

    def drain_until(self, time_ns: int) -> Iterator[Message]:
        """Yield every message whose timestamp is at or before ``time_ns``."""

        while self._heap and self._heap[0][2].time_ns <= time_ns:
            _, _, message = heapq.heappop(self._heap)
            if len(self.journal) < self.journal_limit:
                self.journal.append(message)
            else:
                self.dropped_journal_records += 1
            yield message

    def pending(self) -> int:
        return len(self._heap)

    def clear(self) -> None:
        self._heap.clear()
        self.journal.clear()
        self._sequence.clear()
        self.dropped_journal_records = 0
