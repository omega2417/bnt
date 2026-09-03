"""Ground-truth federate.

Two kinds of truth are recorded and kept apart:

* ``injected`` - the intervals the scenario declared, known before the run;
* ``transition`` - state changes the model actually produced (WAN failover,
  power state, BMS trip, AP loss), which the source MVP could not report.

Labels are never derived from detector output, so leakage is structurally
impossible rather than merely discouraged.
"""

from __future__ import annotations

from typing import Any

from ...core.events import EventIndex
from ...core.federate import Federate

__all__ = ["GroundTruthFederate"]

#: event type -> (cause, expected observable channel)
EXPECTED_OBSERVABLE = {
    "wan_down": ("link_failure", "active_wan_id,failover_active,throughput_mbps"),
    "wan_degrade": ("link_degradation", "loss_pct,rtt_ms,wan_capacity_mbps"),
    "vpn_degrade": ("tunnel_degradation", "vpn_latency_ms,vpn_loss_pct"),
    "wifi_auth_burst": ("synthetic_auth_failures", "auth_failures"),
    "rogue_ap_signal": ("synthetic_bssid", "rogue_ap_count"),
    "recon_burst": ("synthetic_recon", "scan_rate_pps"),
    "lateral_sequence": ("synthetic_lateral", "lateral_events"),
    "low_rate_c2": ("synthetic_c2", "c2_beacons"),
    "traffic_burst": ("load_increase", "offered_load_mbps"),
    "mains_loss": ("mains_failure", "power_state_end,soc_pct,ats_transitions"),
    "telemetry_loss": ("transport_loss", "telemetry_gap_marker"),
    "cell_imbalance": ("cell_deviation", "cell_imbalance_mv"),
    "model_drift": ("distribution_shift", "mean_rssi_dbm,offered_load_mbps"),
    "ap_down": ("ap_outage", "ap_online"),
    "asset_fault": ("asset_fault", "assets_degraded"),
    "charge_start": ("charge_request", "charge_state,pack_current_a"),
    "clock_skew": ("clock_error", "quality_flags"),
    "duplicate_storm": ("transport_duplication", "quality_flags"),
}


class GroundTruthFederate(Federate):
    order = 90

    def __init__(self, events: EventIndex, run_id: str, replicate_id: int,
                 clock_start_iso: str, name: str = "ground_truth") -> None:
        super().__init__(name)
        self.events = events
        self.run_id = run_id
        self.replicate_id = replicate_id
        self.clock_start_iso = clock_start_iso
        self.transitions: list[dict[str, Any]] = []
        self._previous: dict[str, Any] = {}

    def injected_intervals(self, dt_s: float) -> list[dict[str, Any]]:
        rows = []
        for event in self.events.events:
            cause, observable = EXPECTED_OBSERVABLE.get(
                event.event_type, ("unspecified", ""))
            for target in event.targets:
                rows.append({
                    "run_id": self.run_id, "replicate_id": self.replicate_id,
                    "truth_id": f"{event.event_id}:{target}", "kind": "injected",
                    "cause": cause, "site_id": target, "target": target,
                    "stage": event.event_type, "intensity": event.ramp,
                    "onset_utc": self._iso(event.start_s),
                    "end_utc": self._iso(event.end_s),
                    "onset_step": int(event.start_s / dt_s),
                    "end_step": int(event.end_s / dt_s),
                    "expected_observable": observable,
                    "notes": f"params={event.params}",
                })
        return rows

    def _iso(self, offset_s: float) -> str:
        assert self.clock is not None
        from datetime import timedelta
        stamp = self.clock.start_utc + timedelta(seconds=offset_s)
        return stamp.isoformat().replace("+00:00", "Z")

    def advance(self, t_ns: int, dt_ns: int) -> None:
        assert self.clock is not None
        shared = self.context["shared"]
        step = self.clock.step_index
        watch = {
            "power_state": shared.get("power", {}).get("power_state_end"),
            "protection_trip": shared.get("power", {}).get("protection_trip"),
            "shed_groups": tuple(shared.get("power", {}).get("shed_groups", ())),
        }
        for site_id, row in shared.get("network", {}).items():
            watch[f"active_wan:{site_id}"] = row.get("active_wan_id")
            watch[f"vpn_state:{site_id}"] = row.get("vpn_state")
        for site_id, row in shared.get("wifi", {}).items():
            watch[f"ap_online:{site_id}"] = row.get("ap_online")

        for key, value in watch.items():
            previous = self._previous.get(key, value)
            if previous != value:
                self.transitions.append({
                    "run_id": self.run_id, "replicate_id": self.replicate_id,
                    "truth_id": f"transition:{key}:{step}", "kind": "transition",
                    "cause": key, "site_id": key.split(":")[-1] if ":" in key else "site_a",
                    "target": key, "stage": f"{previous}->{value}", "intensity": "",
                    "onset_utc": self.clock.iso(), "end_utc": self.clock.iso(dt_ns),
                    "onset_step": step, "end_step": step + 1,
                    "expected_observable": key, "notes": "",
                })
            self._previous[key] = value

    def observe(self) -> dict[str, Any]:
        return {"transitions": len(self.transitions)}

    def all_truth(self, dt_s: float) -> list[dict[str, Any]]:
        return self.injected_intervals(dt_s) + self.transitions
