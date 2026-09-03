"""Telemetry federate: assembles one contract-valid record per site and step.

It is the only component allowed to produce rows for ``telemetry.csv``. It
applies the sensor and transport imperfections, stamps the three timestamps,
and blanks measurement fields during a telemetry gap while keeping identity
and quality metadata, as required by section 9.11.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.contracts import RecordBuilder, TELEMETRY_FIELDS
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .buffer import StoreAndForwardBuffer
from .sensor import MissingnessModel, Sensor

__all__ = ["TelemetryFederate"]

#: Identity and quality fields that survive a telemetry gap.
GAP_KEEP = ("run_id", "replicate_id", "step", "timestamp_utc", "interval_end_utc",
            "observed_time_utc", "ingest_time_utc", "site_id", "mode", "evidence_class",
            "quality_flags", "telemetry_gap_marker")


class TelemetryFederate(Federate):
    order = 60

    def __init__(self, sites: list[str], events: EventIndex, rng: RngHub,
                 run_id: str, replicate_id: int, mode: str = "SIM",
                 evidence_class: str = "synthetic_demo",
                 defects_enabled: bool = True, name: str = "telemetry") -> None:
        super().__init__(name)
        self.sites = list(sites)
        self.events = events
        self.rng = rng
        self.run_id = run_id
        self.replicate_id = replicate_id
        self.mode = mode
        self.evidence_class = evidence_class
        self.defects_enabled = defects_enabled
        self.rows: list[dict[str, Any]] = []
        self.buffers = {site: StoreAndForwardBuffer() for site in sites}
        self.sensors = {
            "rtt_ms": Sensor("rtt", noise_sd=0.4, quantum=0.01,
                             missingness=MissingnessModel(0.1, 1.0)),
            "throughput_mbps": Sensor("throughput", noise_sd=0.6, quantum=0.01),
            "loss_pct": Sensor("loss", noise_sd=0.02, quantum=0.001),
            "mean_rssi_dbm": Sensor("rssi", noise_sd=0.5, quantum=0.1,
                                    freeze_probability=0.002),
            "soc_pct": Sensor("soc", noise_sd=0.05, quantum=0.01),
            "battery_temp_c": Sensor("temp", noise_sd=0.08, quantum=0.1,
                                     freeze_probability=0.001),
        }
        self.gap_steps = 0

    # -- assembly --------------------------------------------------------
    def _row_for(self, site_id: str, t_s: float, step: int) -> dict[str, Any]:
        shared = self.context["shared"]
        network = shared.get("network", {}).get(site_id, {})
        wifi = shared.get("wifi", {}).get(site_id, {})
        assets = shared.get("assets", {}).get(site_id, {})
        workload = shared.get("workload", {}).get(site_id, {})
        threats = shared.get("threats", {}).get(site_id, {})
        power = shared.get("power", {}) if site_id == "site_a" else {}
        assert self.clock is not None
        start_iso, end_iso = self.clock.interval_iso()

        builder = RecordBuilder()
        builder.set(
            run_id=self.run_id, replicate_id=self.replicate_id, step=step,
            timestamp_utc=start_iso, interval_end_utc=end_iso,
            observed_time_utc=start_iso, ingest_time_utc=end_iso,
            site_id=site_id, mode=self.mode, evidence_class=self.evidence_class,
            active_wan_id=network.get("active_wan_id") or "",
            wan_state=network.get("wan_state", ""),
            wan_capacity_mbps=round(float(network.get("capacity_mbps", 0.0)), 4),
            offered_load_mbps=round(float(network.get("offered_load_mbps", 0.0)), 4),
            throughput_mbps=round(float(network.get("throughput_mbps", 0.0)), 4),
            queue_delay_ms=round(float(network.get("queue_delay_ms", 0.0)), 4),
            rtt_ms=round(float(network.get("rtt_ms", 0.0)), 4),
            jitter_ms=round(float(network.get("jitter_ms", 0.0)), 4),
            loss_pct=round(float(network.get("path_loss_pct", 0.0)), 5),
            failover_active=int(bool(network.get("failover_active", False))),
            vpn_state=network.get("vpn_state", ""),
            vpn_latency_ms=round(float(network.get("vpn_latency_ms", 0.0)), 4),
            vpn_loss_pct=round(float(network.get("vpn_loss_pct", 0.0)), 4),
            ap_total=wifi.get("ap_total", 0), ap_online=wifi.get("ap_online", 0),
            wifi_clients=wifi.get("wifi_clients", 0),
            mean_rssi_dbm=round(float(wifi.get("mean_rssi_dbm", 0.0)), 3),
            channel_util_pct=round(float(wifi.get("channel_util_pct", 0.0)), 3),
            retry_pct=round(float(wifi.get("retry_pct", 0.0)), 3),
            auth_failures=wifi.get("auth_failures", 0),
            roaming_events=wifi.get("roaming_events", 0),
            rogue_ap_count=wifi.get("rogue_ap_count", 0),
            assets_ready=assets.get("assets_ready", 0),
            assets_degraded=assets.get("assets_degraded", 0),
            flows_per_s=round(float(workload.get("flows_per_s", 0.0)), 3),
            scan_rate_pps=round(float(threats.get("scan_rate_pps", 0.0)), 3),
            lateral_events=threats.get("lateral_events", 0),
            c2_beacons=threats.get("c2_beacons", 0),
            power_state_start=power.get("power_state_start", ""),
            power_state_end=power.get("power_state_end", ""),
            mains_present=int(bool(power.get("mains_present", True))) if power else "",
            ats_transitions=power.get("ats_transitions", "") if power else "",
            soc_pct=round(float(power["soc_pct"]), 4) if power else "",
            soh_pct=round(float(power["soh_pct"]), 3) if power else "",
            pack_ocv_v=round(float(power["pack_ocv_v"]), 4) if power else "",
            pack_voltage_v=round(float(power["pack_voltage_v"]), 4) if power else "",
            pack_current_a=round(float(power["pack_current_a"]), 4) if power else "",
            cell_ocv_min_v=round(float(power["cell_ocv_min_v"]), 5) if power else "",
            cell_ocv_max_v=round(float(power["cell_ocv_max_v"]), 5) if power else "",
            cell_min_v=round(float(power["cell_min_v"]), 5) if power else "",
            cell_max_v=round(float(power["cell_max_v"]), 5) if power else "",
            cell_imbalance_mv=round(float(power["cell_imbalance_mv"]), 3) if power else "",
            battery_temp_c=round(float(power["battery_temp_c"]), 3) if power else "",
            load_w=round(float(power["load_w"]), 3) if power else "",
            shed_groups="|".join(str(g) for g in power.get("shed_groups", ())) if power else "",
            autonomy_min=round(float(power["autonomy_min"]), 3) if power else "",
            protection_trip=power.get("protection_trip", "") if power else "",
            charge_state=power.get("charge_state", "") if power else "",
            detector_score="", detector_alert="", alert_latency_s="",
            quality_flags="SYNTHETIC", telemetry_gap_marker=0,
        )
        return builder

    def advance(self, t_ns: int, dt_ns: int) -> None:
        assert self.clock is not None
        t_s = t_ns / 1e9
        step = self.clock.step_index
        shared = self.context["shared"]
        emitted: dict[str, dict[str, Any]] = {}

        for site_id in self.sites:
            rng = self.rng.stream(f"telemetry:{site_id}")
            builder = self._row_for(site_id, t_s, step)
            gap = self.events.any_active(t_s, "telemetry_loss", site_id)
            flags = ["SYNTHETIC"]

            if self.defects_enabled and not gap:
                utilization = float(shared.get("network", {}).get(site_id, {})
                                    .get("utilization", 0.0))
                for field_name, sensor in self.sensors.items():
                    current = builder.values.get(field_name)
                    if current in ("", None):
                        continue
                    reading = sensor.measure(float(current), rng, t_s, utilization)
                    if reading["value"] is None:
                        builder.values[field_name] = ""
                        flags.extend(reading["flags"])
                    else:
                        builder.values[field_name] = round(float(reading["value"]), 5)
                        flags.extend(f for f in reading["flags"] if f != "OK")
                skew = self.events.first(t_s, "clock_skew", site_id)
                if skew is not None:
                    flags.append("CLOCK_SUSPECT")

            if gap:
                self.gap_steps += 1
                keep = {name: builder.values.get(name, "") for name in GAP_KEEP}
                builder.blank_measurements(GAP_KEEP)
                builder.values.update(keep)
                builder.values["telemetry_gap_marker"] = 1
                flags.append("GAP")

            # No usable path means there is nothing to measure: latency-like
            # fields are blanked rather than reported as a 60-second artefact
            # of an empty denominator.
            network = shared.get("network", {}).get(site_id, {})
            if not gap and network.get("path_available") is False:
                for blanked in ("rtt_ms", "queue_delay_ms", "jitter_ms", "loss_pct"):
                    builder.values[blanked] = ""
                flags.append("SATURATED")

            builder.values["quality_flags"] = "|".join(dict.fromkeys(flags))
            row = builder.build()

            transport_up = not gap
            delivered = self.buffers[site_id].offer(row, transport_up, rng) \
                if self.defects_enabled else ([row] if transport_up else [])
            self.rows.extend(delivered)
            emitted[site_id] = row
            self.emit("telemetry", {"site_id": site_id, "step": step,
                                    "delivered": len(delivered)}, Phase.SAMPLING)

        shared["telemetry_row"] = emitted

    def observe(self) -> dict[str, Any]:
        return {"records": len(self.rows), "gap_steps": self.gap_steps,
                "pending": {site: buffer.pending for site, buffer in self.buffers.items()}}

    def health(self) -> FederateHealth:
        backlog = sum(buffer.pending for buffer in self.buffers.values())
        if backlog > 1000:
            return FederateHealth.degraded(self.name, f"buffer backlog {backlog}")
        return FederateHealth.ok(self.name)

    @property
    def fieldnames(self) -> tuple[str, ...]:
        return TELEMETRY_FIELDS
