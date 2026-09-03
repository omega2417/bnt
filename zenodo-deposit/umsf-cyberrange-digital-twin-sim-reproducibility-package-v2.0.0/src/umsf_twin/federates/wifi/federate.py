"""Wi-Fi federate: 54 access points, two controllers, one client population.

Aggregates per-AP behaviour into site-level telemetry and injects the Wi-Fi
scenario events (`wifi_auth_burst`, `rogue_ap_signal`, `ap_down`, drift).
Access points in load-shed groups follow the power federate, so a mains loss
at site A removes auxiliary APs exactly as the runbook expects.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .ap import AccessPoint, ApState
from .clients import ClientPopulation
from .controller import Controller

__all__ = ["WifiFederate"]


class WifiFederate(Federate):
    order = 55

    def __init__(self, sites: dict[str, Any], events: EventIndex, rng: RngHub,
                 name: str = "wifi") -> None:
        super().__init__(name)
        self.events = events
        self.rng = rng
        self.aps: dict[str, list[AccessPoint]] = {}
        self.controllers: dict[str, Controller] = {}
        self.populations: dict[str, ClientPopulation] = {}
        self.metrics: dict[str, dict[str, Any]] = {}

        for site_id, site in sites.items():
            uplinks = dict(site.get("known_ap_uplinks", {}))
            known_1g = int(uplinks.get("1000_mbps", 0))
            known_100m = int(uplinks.get("100_mbps", 0))
            unknown = int(uplinks.get("unknown", 0))
            total = int(site["ap_count"])
            if known_1g + known_100m + unknown != total:
                unknown = max(0, total - known_1g - known_100m)
            fleet: list[AccessPoint] = []
            prefix = "A" if site_id.endswith("a") else "B"
            index = 1
            for count, uplink, group in ((known_1g, 1000.0, 2),
                                         (known_100m, 100.0, 2),
                                         (unknown, None, 3)):
                for _ in range(count):
                    fleet.append(AccessPoint(f"{prefix}-AP-{index:02d}", site_id,
                                             uplink_mbps=uplink, power_group=group))
                    index += 1
            self.aps[site_id] = fleet
            controller = Controller(str(site.get("controller", f"{site_id}-ctrl")), site_id,
                                    "Gen2" if site_id.endswith("a") else "Gen1")
            controller.adopt([ap.ap_id for ap in fleet])
            self.controllers[site_id] = controller
            self.populations[site_id] = ClientPopulation(
                site_id, float(site["baseline"]["clients_mean"]))

    def advance(self, t_ns: int, dt_ns: int) -> None:
        t_s = t_ns / 1e9
        shared = self.context["shared"]
        power = shared.get("power", {})
        shed_groups = set(power.get("shed_groups", ())) if power else set()

        for site_id, fleet in self.aps.items():
            rng = self.rng.stream(f"wifi:{site_id}")
            active = self.events.active(t_s, site_id)
            drift = next((e for e in active if e.event_type == "model_drift"), None)
            auth = next((e for e in active if e.event_type == "wifi_auth_burst"), None)
            rogue = next((e for e in active if e.event_type == "rogue_ap_signal"), None)
            ap_down = next((e for e in active if e.event_type == "ap_down"), None)

            drift_load = float(drift.params["load_factor"]) if drift else 1.0
            rssi_shift = drift.scaled("rssi_shift_db", t_s) if drift else 0.0
            total_clients = self.populations[site_id].draw(self.rng, t_s, drift_load)
            per_ap = self.populations[site_id].spread(total_clients, len(fleet), self.rng)

            forced_off = set()
            if ap_down is not None:
                explicit = [str(x) for x in ap_down.params.get("ap_ids", [])]
                forced_off.update(explicit)
                if not explicit:
                    forced_off.update(ap.ap_id for ap in fleet[:int(ap_down.params["count"])])

            auth_share = 0
            if auth is not None:
                affected = max(1, int(len(fleet) * float(auth.params["ap_fraction"])))
                auth_share = max(1, int(auth.scaled("add_failures_per_step", t_s) / affected))

            rows = []
            for index, ap in enumerate(fleet):
                powered = (ap.power_group not in shed_groups
                           and ap.ap_id not in forced_off)
                burst = auth_share if (auth is not None and index % 4 == 0) else 0
                rows.append(ap.step(
                    rng,
                    clients=per_ap[index] if index < len(per_ap) else 0,
                    rssi_shift_db=rssi_shift,
                    congestion=0.25 if drift else 0.0,
                    auth_burst=burst,
                    powered=powered,
                    rogue_count=int(rogue.params["rogue_count"]) if rogue and index == 0 else 0,
                ))

            online = [row for row in rows if row["state"] != ApState.OFFLINE]
            controller_row = self.controllers[site_id].step(
                reachable=not self.events.any_active(t_s, "telemetry_loss", site_id))
            unknown_uplinks = sum(1 for ap in fleet if not ap.uplink_known)

            self.metrics[site_id] = {
                "site_id": site_id,
                "ap_total": len(fleet),
                "ap_online": len(online),
                "ap_degraded": sum(1 for row in rows if row["state"] == ApState.DEGRADED),
                "wifi_clients": sum(row["clients"] for row in online),
                "mean_rssi_dbm": (sum(row["rssi_dbm"] for row in online) / len(online)
                                  if online else 0.0),
                "channel_util_pct": (sum(row["channel_util_pct"] for row in online) / len(online)
                                     if online else 0.0),
                "retry_pct": (sum(row["retry_pct"] for row in online) / len(online)
                              if online else 0.0),
                "auth_failures": sum(row["auth_failures"] for row in rows),
                "roaming_events": sum(row["roaming_events"] for row in rows),
                "rogue_ap_count": sum(row["rogue_neighbors"] for row in rows),
                "wifi_capacity_mbps": sum(row["effective_capacity_mbps"] for row in online),
                "unknown_uplink_aps": unknown_uplinks,
                "controller": controller_row,
                "quality_flag": "UNKNOWN_UPLINK" if unknown_uplinks else "OK",
            }
            self.emit("wifi_state", {"site_id": site_id,
                                     "ap_online": len(online)}, Phase.TOPOLOGY)
        shared["wifi"] = self.metrics

    def observe(self) -> dict[str, Any]:
        return self.metrics

    def health(self) -> FederateHealth:
        for site_id, row in self.metrics.items():
            if row["ap_online"] == 0:
                return FederateHealth.failed(self.name, f"all APs offline at {site_id}")
        return FederateHealth.ok(self.name)
