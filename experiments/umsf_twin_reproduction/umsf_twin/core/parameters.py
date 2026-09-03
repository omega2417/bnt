"""Parameter registry with mandatory provenance.

Section 3.4 of the specification requires two independent statuses for every
parameter: *what it is* (value/unit) and *where it comes from* (evidence).
This module makes that requirement executable: a parameter cannot enter the
simulation without an evidence status, and a run mode can refuse parameters
whose evidence is weaker than the mode demands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Iterator

from .errors import ParameterError

__all__ = ["EvidenceStatus", "Parameter", "ParameterRegistry", "MODE_MIN_EVIDENCE"]


class EvidenceStatus(IntEnum):
    """Ordered strength of evidence behind a parameter value.

    The ordering is used by :meth:`ParameterRegistry.assert_mode_ready`; a
    higher member is always at least as trustworthy as a lower one.
    """

    UNKNOWN = 0            # not inventoried; must not drive any conclusion
    SYNTHETIC_DEMO = 1     # invented so that the code runs at all
    ASSUMED = 2            # engineering assumption, written down explicitly
    DERIVED = 3            # computed from other parameters
    VENDOR_SPEC = 4        # datasheet / nameplate value
    MEASURED = 5           # measured on the physical cyber range

    @classmethod
    def parse(cls, raw: "str | int | EvidenceStatus") -> "EvidenceStatus":
        if isinstance(raw, EvidenceStatus):
            return raw
        if isinstance(raw, int):
            return cls(raw)
        key = str(raw).strip().upper()
        if key not in cls.__members__:
            raise ParameterError(f"unknown evidence status: {raw!r}")
        return cls[key]


#: Minimum evidence a parameter must carry before a given run mode may use it.
MODE_MIN_EVIDENCE = {
    # SIM tolerates UNKNOWN sentinels: an uninventoried parameter is allowed to
    # exist, it simply may not support any claim about the physical range.
    "SIM": EvidenceStatus.UNKNOWN,
    "EMU": EvidenceStatus.SYNTHETIC_DEMO,
    "REPLAY": EvidenceStatus.SYNTHETIC_DEMO,
    "HIL": EvidenceStatus.VENDOR_SPEC,
}


@dataclass(frozen=True)
class Parameter:
    """A single value plus everything needed to defend it in a paper."""

    name: str
    value: Any
    unit: str = "1"
    evidence: EvidenceStatus = EvidenceStatus.UNKNOWN
    source: str = "unspecified"
    uncertainty: dict[str, Any] | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ParameterError("parameter name must not be empty")
        object.__setattr__(self, "evidence", EvidenceStatus.parse(self.evidence))

    @property
    def is_usable_number(self) -> bool:
        return isinstance(self.value, (int, float)) and not isinstance(self.value, bool)

    def as_float(self) -> float:
        if not self.is_usable_number:
            raise ParameterError(f"{self.name} is not numeric: {self.value!r}")
        return float(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "evidence_status": self.evidence.name,
            "source": self.source,
            "uncertainty": self.uncertainty,
            "note": self.note,
        }


class ParameterRegistry:
    """Append-only store of parameters, freezable before a run starts."""

    def __init__(self, mode: str = "SIM") -> None:
        self._items: dict[str, Parameter] = {}
        self._frozen = False
        self.mode = mode

    def register(self, parameter: Parameter) -> Parameter:
        if self._frozen:
            raise ParameterError(f"registry frozen; cannot add {parameter.name}")
        if parameter.name in self._items and self._items[parameter.name] != parameter:
            raise ParameterError(f"conflicting redefinition of {parameter.name}")
        self._items[parameter.name] = parameter
        return parameter

    def add(self, name: str, value: Any, unit: str = "1", evidence: Any = "SYNTHETIC_DEMO",
            source: str = "demo-config", uncertainty: dict[str, Any] | None = None,
            note: str = "") -> Parameter:
        return self.register(Parameter(name, value, unit, EvidenceStatus.parse(evidence),
                                       source, uncertainty, note))

    def ingest_config(self, config: dict[str, Any], prefix: str = "") -> None:
        """Flatten a nested config into the registry.

        Scalars become parameters whose evidence is taken from the enclosing
        document's ``evidence_class`` unless the value itself is the sentinel
        ``"UNINVENTORIED"``, which always maps to :data:`EvidenceStatus.UNKNOWN`.
        """

        default = str(config.get("evidence_class", "synthetic_demo")).upper()
        default_status = EvidenceStatus.parse(
            "SYNTHETIC_DEMO" if default.startswith("SYNTHETIC") else default
        )

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}" if path else str(key))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}[{index}]")
            else:
                status = (EvidenceStatus.UNKNOWN
                          if isinstance(node, str) and node.upper() == "UNINVENTORIED"
                          else default_status)
                name = f"{prefix}{path}"
                if name not in self._items:
                    self.register(Parameter(name, node, "1", status, "config"))

        walk(config, "")

    def get(self, name: str) -> Parameter:
        try:
            return self._items[name]
        except KeyError as exc:
            raise ParameterError(f"parameter not registered: {name}") from exc

    def require(self, name: str, minimum: Any = EvidenceStatus.ASSUMED) -> Parameter:
        parameter = self.get(name)
        floor = EvidenceStatus.parse(minimum)
        if parameter.evidence < floor:
            raise ParameterError(
                f"{name} has evidence {parameter.evidence.name}, "
                f"but {floor.name} or stronger is required"
            )
        return parameter

    def unknowns(self) -> list[str]:
        return sorted(n for n, p in self._items.items()
                      if p.evidence == EvidenceStatus.UNKNOWN)

    def weaker_than(self, minimum: Any) -> list[str]:
        floor = EvidenceStatus.parse(minimum)
        return sorted(n for n, p in self._items.items() if p.evidence < floor)

    def assert_mode_ready(self, mode: str | None = None) -> None:
        """Refuse to run a mode that its parameters cannot support."""

        mode = (mode or self.mode).upper()
        floor = MODE_MIN_EVIDENCE.get(mode)
        if floor is None:
            raise ParameterError(f"unknown run mode: {mode}")
        offenders = self.weaker_than(floor)
        if offenders:
            raise ParameterError(
                f"mode {mode} requires evidence >= {floor.name}; "
                f"{len(offenders)} parameter(s) below it, e.g. {offenders[:5]}"
            )

    def freeze(self) -> "ParameterRegistry":
        self._frozen = True
        return self

    @property
    def frozen(self) -> bool:
        return self._frozen

    def table(self) -> list[dict[str, Any]]:
        return [self._items[name].to_dict() for name in sorted(self._items)]

    def evidence_histogram(self) -> dict[str, int]:
        histogram = {status.name: 0 for status in EvidenceStatus}
        for parameter in self._items.values():
            histogram[parameter.evidence.name] += 1
        return histogram

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Parameter]:
        return iter(self._items[name] for name in sorted(self._items))

    def __contains__(self, name: object) -> bool:
        return name in self._items
