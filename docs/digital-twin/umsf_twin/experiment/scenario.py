"""Scenario compiler and validator (section 11.4).

A scenario is only runnable when it satisfies three things at once: the JSON
schema, the safety policy and the documented inventory invariants. The
compiler checks all three and produces a frozen, hashable object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.errors import ConfigError, InvariantViolation
from ..core.events import ScenarioEvent
from ..core.parameters import ParameterRegistry
from ..core.provenance import canonical_hash
from ..core.safety import SafetyPolicy

__all__ = ["Scenario", "load_scenario", "REQUIRED_SITE_KEYS", "check_inventory_invariants"]

REQUIRED_SITE_KEYS = ("ap_count", "wan_links", "baseline")
REQUIRED_BASELINE_KEYS = ("offered_load_mbps", "clients_mean", "mean_rssi_dbm")

#: Documented counts from the source DOCX. They are invariants of the *model*,
#: not measurements: if the physical inventory disagrees, the config changes,
#: never the check.
DOCUMENTED_INVARIANTS = {
    "site_a": {"ap_count": 48, "wan_count": 5},
    "site_b": {"ap_count": 6, "wan_count": 2, "kali_workstations": 25},
}


def check_inventory_invariants(config: dict[str, Any], strict: bool = True) -> list[str]:
    """Return the list of invariant deviations; raise when ``strict``."""

    problems: list[str] = []
    for site_id, expected in DOCUMENTED_INVARIANTS.items():
        site = config.get("sites", {}).get(site_id)
        if site is None:
            problems.append(f"{site_id}: missing from the inventory")
            continue
        if int(site.get("ap_count", -1)) != expected["ap_count"]:
            problems.append(f"{site_id}: ap_count {site.get('ap_count')} "
                            f"!= documented {expected['ap_count']}")
        if len(site.get("wan_links", [])) != expected["wan_count"]:
            problems.append(f"{site_id}: {len(site.get('wan_links', []))} WAN links "
                            f"!= documented {expected['wan_count']}")
        if "kali_workstations" in expected and \
                int(site.get("kali_workstations", -1)) != expected["kali_workstations"]:
            problems.append(f"{site_id}: kali_workstations "
                            f"{site.get('kali_workstations')} != 25")
    if problems and strict:
        raise InvariantViolation("; ".join(problems))
    return problems


@dataclass(frozen=True)
class Scenario:
    experiment_id: str
    config: dict[str, Any]
    events: tuple[ScenarioEvent, ...]
    policy: SafetyPolicy
    registry: ParameterRegistry
    config_hash: str
    invariant_notes: tuple[str, ...] = field(default=())

    @property
    def duration_s(self) -> int:
        return int(self.config["duration_s"])

    @property
    def dt_s(self) -> float:
        return float(self.config.get("dt_s", 1))

    @property
    def sites(self) -> dict[str, Any]:
        return self.config["sites"]

    @property
    def seed(self) -> int:
        return int(self.config["seed"])

    def materialized(self) -> dict[str, Any]:
        """Config with every event default made explicit before hashing."""

        payload = json.loads(json.dumps(self.config))
        payload["events"] = [event.to_dict() for event in self.events]
        return payload


def _validate_structure(config: dict[str, Any]) -> None:
    for key in ("experiment_id", "seed", "start_utc", "duration_s", "sites", "power"):
        if key not in config:
            raise ConfigError(f"config is missing required key {key!r}")
    if not isinstance(config["sites"], dict) or not config["sites"]:
        raise ConfigError("config.sites must be a non-empty object")
    for site_id, site in config["sites"].items():
        for key in REQUIRED_SITE_KEYS:
            if key not in site:
                raise ConfigError(f"sites.{site_id} is missing {key!r}")
        for key in REQUIRED_BASELINE_KEYS:
            if key not in site["baseline"]:
                raise ConfigError(f"sites.{site_id}.baseline is missing {key!r}")
        priorities = [int(link["priority"]) for link in site["wan_links"]]
        if len(set(priorities)) != len(priorities):
            raise ConfigError(f"sites.{site_id}: duplicate WAN priorities")
        ids = [str(link["id"]) for link in site["wan_links"]]
        if len(set(ids)) != len(ids):
            raise ConfigError(f"sites.{site_id}: duplicate WAN ids")


def load_scenario(path: str | Path, policy: SafetyPolicy | None = None,
                  strict_invariants: bool = True,
                  overrides: dict[str, Any] | None = None) -> Scenario:
    """Read, validate and compile a scenario document."""

    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if overrides:
        config = _deep_update(config, overrides)
    _validate_structure(config)
    policy = policy or SafetyPolicy(mode=str(config.get("mode", "SIM")))
    policy.check_mode()

    duration_s = int(config["duration_s"])
    raw_events = list(config.get("events", []))
    policy.check_budget(duration_s, len(raw_events), int(config.get("replicates", 1)))

    seen_ids: set[str] = set()
    events = []
    for raw in raw_events:
        event = ScenarioEvent.from_dict(raw, duration_s, policy)
        if event.event_id in seen_ids:
            raise ConfigError(f"duplicate event_id {event.event_id}")
        seen_ids.add(event.event_id)
        events.append(event)

    notes = check_inventory_invariants(config, strict=strict_invariants)
    registry = ParameterRegistry(mode=policy.mode)
    registry.ingest_config(config)
    registry.freeze()

    materialized = json.loads(json.dumps(config))
    materialized["events"] = [event.to_dict() for event in events]
    return Scenario(
        experiment_id=str(config["experiment_id"]),
        config=config,
        events=tuple(events),
        policy=policy,
        registry=registry,
        config_hash=canonical_hash(materialized),
        invariant_notes=tuple(notes),
    )


def _deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    output = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(output.get(key), dict):
            output[key] = _deep_update(output[key], value)
        else:
            output[key] = value
    return output
