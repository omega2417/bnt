"""MQTT-like transport between the ESP32 edge and the PC twin/EMS.

Emulates per-message one-way latency (log-normal), loss, QoS-1 duplicate
delivery and a test-interface blackout (E06). Messages are delivered in
simulated time; ordering follows arrival time.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

import numpy as np


@dataclass(order=True)
class _Item:
    t_arrive: float
    seq: int
    topic: str = field(compare=False)
    payload: dict = field(compare=False)


class Channel:
    def __init__(self, net: dict, rng: np.random.Generator):
        self.med = net["latency_median_ms"] / 1000.0
        self.sigma = net["latency_sigma"]
        self.loss = net["loss_prob"]
        self.dup = net["dup_prob"]
        self.rng = rng
        self.q: list[_Item] = []
        self.counter = itertools.count()
        self.blackouts: list[tuple[float, float, str]] = []  # (t0, t1, direction)
        self.stats = {"sent": 0, "lost": 0, "dup": 0, "blocked": 0}

    def _blocked(self, t: float, direction: str) -> bool:
        return any(t0 <= t < t1 and d in (direction, "both") for t0, t1, d in self.blackouts)

    def latency(self) -> float:
        return float(self.med * np.exp(self.rng.normal(0, self.sigma)))

    def send(self, t: float, topic: str, payload: dict, direction: str) -> None:
        self.stats["sent"] += 1
        if self._blocked(t, direction):
            self.stats["blocked"] += 1
            return
        if self.rng.random() < self.loss:
            self.stats["lost"] += 1
            return
        heapq.heappush(self.q, _Item(t + self.latency(), next(self.counter), topic, dict(payload)))
        if self.rng.random() < self.dup:  # QoS-1 redelivery
            self.stats["dup"] += 1
            heapq.heappush(self.q, _Item(t + self.latency() + 0.2, next(self.counter), topic, dict(payload)))

    def deliver(self, t: float):
        out = []
        while self.q and self.q[0].t_arrive <= t:
            it = heapq.heappop(self.q)
            out.append((it.t_arrive, it.topic, it.payload))
        return out
