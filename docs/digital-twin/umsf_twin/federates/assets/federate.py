"""Asset federate: advances every node and reports aggregate readiness."""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .asset import Asset, AssetState
from .fleet import build_fleet

__all__ = ["AssetFederate"]


class AssetFederate(Federate):
    order = 30

    def __init__(self, sites: dict[str, Any], events: EventIndex, rng: RngHub,
                 name: str = "assets") -> None:
        super().__init__(name)
        self.events = events
        self.rng = rng
        self.fleet = build_fleet(sites)
        self.metrics: dict[str, dict[str, Any]] = {}

    def all_assets(self) -> list[Asset]:
        return [asset for assets in self.fleet.values() for asset in assets]

    def advance(self, t_ns: int, dt_ns: int) -> None:
        t_s, dt_s = t_ns / 1e9, dt_ns / 1e9
        shared = self.context["shared"]
        power = shared.get("power", {})
        shed_groups = set(power.get("shed_groups", ()))
        site_a_isolated = bool(power.get("isolated", False))

        for site_id, assets in self.fleet.items():
            rng = self.rng.stream(f"assets:{site_id}")
            active = self.events.active(t_s, site_id)
            fault = next((e for e in active if e.event_type == "asset_fault"), None)
            burst = next((e for e in active if e.event_type == "traffic_burst"), None)
            load_factor = 1.0 + (0.6 if burst else 0.0)

            faulted = set(str(x) for x in fault.params.get("asset_ids", [])) if fault else set()
            rows = []
            for asset in assets:
                if asset.asset_id in faulted:
                    asset.inject_fault(str(fault.params.get("fault", "DEGRADED")))
                powered = not (site_id == "site_a"
                               and (asset.power_group in shed_groups or site_a_isolated))
                rows.append(asset.step(dt_s, rng, powered=powered,
                                       load_factor=load_factor))

            ready = [row for row in rows if row["state"] == AssetState.READY]
            self.metrics[site_id] = {
                "site_id": site_id,
                "assets_total": len(rows),
                "assets_ready": len(ready),
                "assets_degraded": sum(1 for row in rows
                                       if row["state"] == AssetState.DEGRADED),
                "assets_off": sum(1 for row in rows if row["state"] == AssetState.OFF),
                "kali_ready": sum(1 for row in ready if row["role"] == "kali_workstation"),
                "asset_power_w": sum(row["power_w"] for row in rows),
                "mean_utilization": (sum(row["utilization"] for row in ready) / len(ready)
                                     if ready else 0.0),
                "rows": rows,
            }
            self.emit("asset_state", {"site_id": site_id,
                                      "ready": len(ready)}, Phase.POWER_ASSET)
        shared["assets"] = self.metrics
        shared["asset_power_w"] = {site: row["asset_power_w"]
                                   for site, row in self.metrics.items()}

    def observe(self) -> dict[str, Any]:
        return {site: {k: v for k, v in row.items() if k != "rows"}
                for site, row in self.metrics.items()}

    def health(self) -> FederateHealth:
        for site_id, row in self.metrics.items():
            if row["assets_ready"] == 0:
                return FederateHealth.failed(self.name, f"no ready asset at {site_id}")
        return FederateHealth.ok(self.name)
