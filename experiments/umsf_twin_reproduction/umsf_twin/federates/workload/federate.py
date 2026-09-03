"""Workload federate: turns the service mix into offered load per site.

The offered load is the *demand* seen by the network federate. It is produced
from a first-order autoregressive baseline plus the per-service processes, so
consecutive steps are correlated the way real traffic is, and a burst event
adds a bounded, safety-clamped increment on top.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate
from ...core.rng import RngHub
from .services import DEFAULT_SERVICES, ServiceProfile, seasonal_factor

__all__ = ["WorkloadFederate"]


class WorkloadFederate(Federate):
    order = 40

    def __init__(self, sites: dict[str, Any], events: EventIndex, rng: RngHub,
                 services: tuple[ServiceProfile, ...] = DEFAULT_SERVICES,
                 name: str = "workload") -> None:
        super().__init__(name)
        self.events = events
        self.rng = rng
        self.sites = sites
        # The reference service mix is defined at a 140 Mbps site; each site
        # scales it by its own baseline so a small site does not inherit a
        # large site's flow volume.
        self.services = {}
        for site_id, site in sites.items():
            scale = float(site["baseline"]["offered_load_mbps"]) / 140.0
            self.services[site_id] = tuple(
                ServiceProfile(**{**vars(profile),
                                  "flows_mean": profile.flows_mean * scale,
                                  "_excitation": 0.0})
                for profile in services)
        self.level = {site_id: float(site["baseline"]["offered_load_mbps"])
                      for site_id, site in sites.items()}
        self.metrics: dict[str, dict[str, Any]] = {}

    def advance(self, t_ns: int, dt_ns: int) -> None:
        t_s = t_ns / 1e9
        shared = self.context["shared"]
        policy = self.context["policy"]
        assets = shared.get("assets", {})

        for site_id, site in self.sites.items():
            baseline = site["baseline"]
            active = self.events.active(t_s, site_id)
            drift = next((e for e in active if e.event_type == "model_drift"), None)
            burst = next((e for e in active if e.event_type == "traffic_burst"), None)
            load_factor = float(drift.params["load_factor"]) if drift else 1.0

            season = seasonal_factor(t_s)
            service_rows = {profile.name: profile.step(self.rng, t_s, season, load_factor)
                            for profile in self.services[site_id]}
            service_mbps = sum(row["mbps"] for row in service_rows.values())

            # AR(1) baseline keeps step-to-step correlation realistic.
            phi = float(baseline.get("ar_coefficient", 0.94))
            noise = self.rng.normal(f"background:{site_id}", 0.0,
                                    float(baseline.get("load_noise_sd", 5.0)))
            target = float(baseline["offered_load_mbps"]) * season * load_factor
            self.level[site_id] = phi * self.level[site_id] + (1.0 - phi) * target + noise

            readiness = 1.0
            site_assets = assets.get(site_id)
            if site_assets and site_assets["assets_total"]:
                readiness = site_assets["assets_ready"] / site_assets["assets_total"]

            # The AR(1) level represents the aggregate background demand; the
            # service mix contributes an explicitly configurable share on top,
            # so the identified-traffic fraction is a parameter rather than a
            # constant buried in the code.
            coupling = float(site.get("service_load_coupling", 0.05))
            offered = max(0.0, self.level[site_id]) * (0.4 + 0.6 * readiness) \
                + coupling * service_mbps
            if burst is not None:
                offered += burst.scaled("add_mbps", t_s)
            offered = policy.clamp_load(offered)

            self.metrics[site_id] = {
                "site_id": site_id,
                "offered_load_mbps": offered,
                "flows_per_s": sum(row["flows"] for row in service_rows.values()),
                "service_mix": {name: round(row["mbps"], 4)
                                for name, row in service_rows.items()},
                "seasonal_factor": season,
                "readiness_factor": readiness,
                "compute_add_w": (burst.scaled("compute_add_w", t_s) if burst else 0.0),
            }
            self.emit("workload", {"site_id": site_id, "offered_mbps": offered}, Phase.FLOWS)

        shared["workload"] = self.metrics
        shared["offered_load_mbps"] = {site: row["offered_load_mbps"]
                                       for site, row in self.metrics.items()}
        shared["compute_add_w"] = {site: row["compute_add_w"]
                                   for site, row in self.metrics.items()}

    def observe(self) -> dict[str, Any]:
        return self.metrics
