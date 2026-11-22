"""Deterministic publish/subscribe message bus for the multi-agent system.

The topics of the bus are exactly the buses of the structural model
(X, XiWK, O, M, A, G, R, P, C) plus operational topics (telemetry, alert,
forecast, advice, report). Every message is logged, so the dynamic mode of the
system can be replayed and drawn as a sequence diagram.
"""
from __future__ import annotations

import itertools
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Message:
    topic: str
    sender: str
    payload: Any
    corr: int = 0                 # correlation id = one assessment run
    tick: int = 0                 # simulation time
    seq: int = 0                  # global order
    meta: dict = field(default_factory=dict)


class MessageBus:
    def __init__(self, keep_log: bool = True, max_log: int = 200_000):
        self._subs: dict[str, list[Callable[[Message], None]]] = defaultdict(list)
        self._queue: deque[Message] = deque()
        self._seq = itertools.count()
        self._dispatching = False
        self.log: list[Message] = []
        self.keep_log = keep_log
        self.max_log = max_log
        self.tick = 0

    def subscribe(self, topic: str, handler: Callable[[Message], None]) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, sender: str, payload: Any, corr: int = 0, **meta) -> Message:
        msg = Message(topic, sender, payload, corr, self.tick, next(self._seq), meta)
        self._queue.append(msg)
        if self.keep_log and len(self.log) < self.max_log:
            self.log.append(msg)
        if not self._dispatching:
            self._drain()
        return msg

    def _drain(self) -> None:
        self._dispatching = True
        try:
            while self._queue:
                msg = self._queue.popleft()
                for h in list(self._subs.get(msg.topic, ())) + list(self._subs.get("*", ())):
                    h(msg)
        finally:
            self._dispatching = False

    def messages(self, topic: str | None = None, corr: int | None = None) -> list[Message]:
        return [m for m in self.log if (topic is None or m.topic == topic)
                and (corr is None or m.corr == corr)]


class Agent:
    """Base class: an agent has a name, subscribes to topics and publishes messages."""

    name: str = "agent"
    role: str = ""

    def __init__(self, bus: MessageBus, name: str | None = None):
        self.bus = bus
        if name:
            self.name = name
        self.inbox_count = 0

    def on(self, topic: str, handler: Callable[[Message], None]) -> None:
        def wrapped(msg: Message):
            self.inbox_count += 1
            handler(msg)
        self.bus.subscribe(topic, wrapped)

    def send(self, topic: str, payload: Any, corr: int = 0, **meta) -> Message:
        return self.bus.publish(topic, self.name, payload, corr, **meta)
