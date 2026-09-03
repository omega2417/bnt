"""Network federate: binds links, routers, queues and the VPN into one plane.

Reads the offered load produced by the workload and threat federates, applies
the scenario events addressed to the network, and publishes per-site path
metrics (throughput, RTT, jitter, loss, failover state) for telemetry.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .queue import FluidQueue
from .router import MultiWanRouter
from .vpn import VpnTunnel
from .wan import WanLink, WanState

__all__ = ["NetworkFederate"]


class NetworkFederate(Federate):
    order = 50

    def __init__(self, sites: dict[str, Any], vpn_config: dict[str, Any],
                 events: EventIndex, rng: RngHub, name: str = "network") -> None:
        super().__init__(name)
        self.events = events
        self.rng = rng
        self.routers: dict[str, MultiWanRouter] = {}
        self.queues: dict[str, FluidQueue] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        for site_id, site in sites.items():
            links = [WanLink.from_config(raw, site_id) for raw in site["wan_links"]]
            self.routers[site_id] = MultiWanRouter(
                router_id=str(site.get("router", site_id)),
                site_id=site_id,
                links=links,
                policy=str(site.get("wan_policy", "primary_backup")),
                failover_delay_s=float(site.get("failover_delay_s", 5)),
                hysteresis_s=float(site.get("wan_hysteresis_s", 15)),
                session_survival_pct=float(site.get("session_survival_pct", 35)),
            )
            self.queues[site_id] = FluidQueue(name=f"{site_id}-egress")
        self.vpn = VpnTunnel(
            base_overhead_ms=float(vpn_config.get("base_overhead_ms", 4.0)),
            mtu=vpn_config.get("mtu", "UNINVENTORIED"),
            protocol=vpn_config.get("protocol", "UNINVENTORIED"),
            rekey_period_s=int(vpn_config.get("rekey_period_s", 3600)),
        )

    # -- helpers ---------------------------------------------------------
    def _apply_events(self, site_id: str, t_s: float) -> None:
        router = self.routers[site_id]
        active = self.events.active(t_s, site_id)
        down_ids = {event.params.get("link_id")
                    for event in active if event.event_type == "wan_down"}
        degrades = [event for event in active if event.event_type == "wan_degrade"]
        for link in router.links:
            degrade = next((event for event in degrades
                            if event.params.get("link_id") in (None, link.link_id)), None)
            link.apply_scenario(
                down=(link.link_id in down_ids or None in down_ids),
                capacity_factor=(degrade.params["capacity_factor"] if degrade else 1.0),
                latency_add_ms=(degrade.scaled("latency_add_ms", t_s) if degrade else 0.0),
                loss_add_pct=(degrade.scaled("loss_add_pct", t_s) if degrade else 0.0),
            )
        vpn_event = self.events.first(t_s, "vpn_degrade", site_id)
        if vpn_event is not None:
            self.vpn.apply_scenario(
                latency_add_ms=vpn_event.scaled("latency_add_ms", t_s),
                loss_add_pct=vpn_event.scaled("loss_add_pct", t_s),
                rekey=bool(vpn_event.params.get("rekey")),
                t_s=t_s,
            )
        elif site_id == "site_a":
            self.vpn.apply_scenario(latency_add_ms=0.0, loss_add_pct=0.0, t_s=t_s)

    # -- federate API ----------------------------------------------------
    def advance(self, t_ns: int, dt_ns: int) -> None:
        assert self.clock is not None
        t_s, dt_s = t_ns / 1e9, dt_ns / 1e9
        shared = self.context["shared"]
        offered = shared.get("offered_load_mbps", {})
        policy = self.context["policy"]

        for site_id, router in self.routers.items():
            self._apply_events(site_id, t_s)
            rng = self.rng.stream(f"network:{site_id}")
            load_mbps = policy.clamp_load(float(offered.get(site_id, 0.0)))

            capacity_hint = max(1.0, sum(link.effective_capacity
                                         for link in router.usable_links()))
            utilization = min(1.0, load_mbps / capacity_hint)
            link_rows = [link.step(t_s, rng, utilization) for link in router.links]
            route = router.step(t_s, rng)

            capacity = route["capacity_mbps"]
            queue = self.queues[site_id].step(load_mbps, capacity, dt_s)
            active_row = next((row for row in link_rows
                               if row["link_id"] == route["active_wan_id"]), None)
            base_rtt = route["base_rtt_ms"]
            jitter = active_row["jitter_ms"] if active_row else 0.0
            loss = active_row["loss_pct"] if active_row else 100.0

            vpn_row = self.vpn.step(t_s, rng, underlay_up=capacity > 0.0) \
                if site_id == "site_a" else dict(self._last_vpn)
            self._last_vpn = vpn_row

            self.metrics[site_id] = {
                **route,
                **queue,
                **vpn_row,
                "site_id": site_id,
                "offered_load_mbps": load_mbps,
                "rtt_ms": base_rtt + queue["queue_delay_ms"] + jitter + vpn_row["vpn_latency_ms"],
                "jitter_ms": jitter,
                "loss_pct": min(100.0, loss + vpn_row["vpn_loss_pct"] * 0.0),
                "path_loss_pct": min(100.0, loss),
                "links": link_rows,
                "link_states": {row["link_id"]: row["state"] for row in link_rows},
                "utilization": queue["utilization"],
            }
            self.emit("network_state", {"site_id": site_id,
                                        "active_wan_id": route["active_wan_id"],
                                        "wan_state": route["wan_state"]}, Phase.TOPOLOGY)
        shared["network"] = self.metrics

    _last_vpn: dict[str, Any] = {"vpn_state": "UP", "vpn_latency_ms": 4.0,
                                 "vpn_loss_pct": 0.0, "vpn_carrying": True,
                                 "vpn_reconnects": 0, "vpn_rekeys": 0,
                                 "vpn_buffered_records": 0, "vpn_burst_delivered": 0,
                                 "mtu_status": "UNINVENTORIED"}

    def observe(self) -> dict[str, Any]:
        return {site: {k: v for k, v in row.items() if k != "links"}
                for site, row in self.metrics.items()}

    def health(self) -> FederateHealth:
        dead = [site for site, router in self.routers.items() if not router.usable_links()]
        if dead:
            return FederateHealth.failed(self.name, f"no usable WAN at {dead}")
        degraded = [site for site, row in self.metrics.items()
                    if row.get("wan_state") == WanState.DEGRADED]
        if degraded:
            return FederateHealth.degraded(self.name, f"degraded WAN at {degraded}")
        return FederateHealth.ok(self.name)

    def reset(self) -> None:
        for router in self.routers.values():
            router.reset()
        for queue in self.queues.values():
            queue.reset()
        self.vpn.reset()
        self.metrics.clear()
