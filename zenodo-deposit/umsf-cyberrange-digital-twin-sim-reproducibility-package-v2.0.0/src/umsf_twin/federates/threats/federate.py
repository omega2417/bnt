"""Threat federate: feature-level effects of the synthetic event catalogue.

Every profile changes *observable features and event counters only*. The
federate asks the safety policy before it touches anything, and it has no code
path that emits a packet, opens a socket or names an external target.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.errors import SafetyViolation
from ...core.rng import RngHub
from .kill_chain import KillChain

__all__ = ["ThreatFederate", "THREAT_PROFILES"]

#: event type -> observable channel it perturbs (documentation and gates use it)
THREAT_PROFILES = {
    "recon_burst": "connection_and_port_counters",
    "lateral_sequence": "asset_to_asset_graph_edges",
    "low_rate_c2": "periodic_flow_records",
    "wifi_auth_burst": "auth_failure_counters",
    "rogue_ap_signal": "bssid_inventory",
    "traffic_burst": "offered_load",
    "model_drift": "feature_distribution",
}


class ThreatFederate(Federate):
    order = 45

    def __init__(self, sites: dict[str, Any], events: EventIndex, rng: RngHub,
                 name: str = "threats") -> None:
        super().__init__(name)
        self.events = events
        self.rng = rng
        self.chains = {site_id: KillChain(f"campaign-{site_id}", site_id)
                       for site_id in sites}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.c2_last_beacon_s: dict[str, float] = {site: -1e9 for site in sites}

    def on_initialize(self) -> None:
        policy = self.context["policy"]
        for event_type in THREAT_PROFILES:
            policy.check_event_type(event_type)
        if policy.allow_external_egress:
            raise SafetyViolation("threat federate refuses to run with egress enabled")

    def advance(self, t_ns: int, dt_ns: int) -> None:
        t_s, dt_s = t_ns / 1e9, dt_ns / 1e9
        shared = self.context["shared"]

        for site_id, chain in self.chains.items():
            rng = self.rng.stream(f"threats:{site_id}")
            active = self.events.active(t_s, site_id)
            types = {event.event_type for event in active}
            adversarial = bool(types & {"recon_burst", "lateral_sequence",
                                        "low_rate_c2", "wifi_auth_burst"})
            chain_row = chain.step(t_s, dt_s, rng, adversarial)

            recon = next((e for e in active if e.event_type == "recon_burst"), None)
            lateral = next((e for e in active if e.event_type == "lateral_sequence"), None)
            c2 = next((e for e in active if e.event_type == "low_rate_c2"), None)
            rogue = next((e for e in active if e.event_type == "rogue_ap_signal"), None)

            scan_rate = recon.scaled("scan_rate_pps", t_s) if recon else 0.0
            unique_ports = int(recon.params["unique_ports"]) if recon else 0
            lateral_events = int(lateral.scaled("events_per_step", t_s)) if lateral else 0

            beacons = 0
            if c2 is not None:
                period = max(1, int(c2.params["period_s"]))
                if t_s - self.c2_last_beacon_s[site_id] >= period:
                    beacons = 1
                    self.c2_last_beacon_s[site_id] = t_s

            self.metrics[site_id] = {
                "site_id": site_id,
                "scan_rate_pps": scan_rate,
                "unique_ports": unique_ports,
                "lateral_events": lateral_events,
                "c2_beacons": beacons,
                "rogue_ap_count": int(rogue.params["rogue_count"]) if rogue else 0,
                "adversarial_active": adversarial,
                "attack_stage": chain_row["stage"],
                "attack_stage_index": chain_row["stage_index"],
                "profiles_active": sorted(types & set(THREAT_PROFILES)),
                "synthetic_only": True,
            }
            if adversarial:
                self.emit("threat_stage", {"site_id": site_id,
                                           "stage": chain_row["stage"]}, Phase.FLOWS)
        shared["threats"] = self.metrics

    def observe(self) -> dict[str, Any]:
        return self.metrics

    def health(self) -> FederateHealth:
        return FederateHealth.ok(self.name, synthetic_only=True)
