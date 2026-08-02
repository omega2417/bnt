"""Shared incident blackboard: the common store the five agents read/write."""

from __future__ import annotations

import json
from pathlib import Path

from ..schemas import Incident

__all__ = ["Blackboard"]


class Blackboard:
    def __init__(self) -> None:
        self._incidents: list[Incident] = []
        self._counter = 0

    def new_incident(self) -> Incident:
        self._counter += 1
        inc = Incident(incident_id=f"INC-{self._counter:06d}")
        self._incidents.append(inc)
        return inc

    @property
    def incidents(self) -> list[Incident]:
        return self._incidents

    def to_records(self) -> list[dict]:
        return [inc.model_dump() for inc in self._incidents]

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_records(), fh, indent=2, default=str)
        return path
