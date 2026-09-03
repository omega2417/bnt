"""Store-and-forward buffer with burst delivery, duplicates and reordering.

When the transport is down the collector keeps records locally; when it comes
back they arrive late, sometimes duplicated and rarely in order. Detectors
that were only ever tested on clean, ordered input fail exactly here, which is
why this behaviour is part of the twin rather than an afterthought.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

__all__ = ["StoreAndForwardBuffer"]


@dataclass
class StoreAndForwardBuffer:
    capacity: int = 10_000
    burst_release: int = 25
    duplicate_pct: float = 0.5
    reorder_pct: float = 2.0
    queue: deque = field(default_factory=deque)
    dropped_overflow: int = 0
    delivered: int = 0
    duplicated: int = 0
    reordered: int = 0

    def offer(self, record: dict[str, Any], transport_up: bool,
              rng: random.Random) -> list[dict[str, Any]]:
        """Return the records actually delivered this step."""

        if not transport_up:
            if len(self.queue) >= self.capacity:
                self.dropped_overflow += 1
            else:
                self.queue.append(record)
            return []

        released = [record]
        for _ in range(min(self.burst_release, len(self.queue))):
            buffered = self.queue.popleft()
            buffered = dict(buffered)
            flags = str(buffered.get("quality_flags", "")).split("|") if buffered.get(
                "quality_flags") else []
            if "OUT_OF_ORDER" not in flags:
                flags.append("OUT_OF_ORDER")
            buffered["quality_flags"] = "|".join(flag for flag in flags if flag)
            released.append(buffered)

        output: list[dict[str, Any]] = []
        for item in released:
            output.append(item)
            if rng.random() * 100.0 < self.duplicate_pct:
                duplicate = dict(item)
                flags = str(duplicate.get("quality_flags", "")).split("|")
                duplicate["quality_flags"] = "|".join([f for f in flags if f] + ["DUPLICATE"])
                output.append(duplicate)
                self.duplicated += 1
        if len(output) > 1 and rng.random() * 100.0 < self.reorder_pct:
            index = rng.randrange(len(output) - 1)
            output[index], output[index + 1] = output[index + 1], output[index]
            self.reordered += 1
        self.delivered += len(output)
        return output

    @property
    def pending(self) -> int:
        return len(self.queue)
