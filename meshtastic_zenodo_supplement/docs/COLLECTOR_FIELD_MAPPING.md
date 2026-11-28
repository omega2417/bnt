# Input fields and the event log of the collector

The article mentions this prototype only because it fixes the input fields that the event log must record during
the planned field experiment. This table states which of those fields the Meshtastic Logistics Metadata Collector
(reference [54], version 1.1.0) already stores and which it does not. Neither program has been run on radio
hardware; "stored" means that a column exists and is filled from the generated test log.

| Prototype field | Collector 1.1.0 | Remark |
|---|---|---|
| `rssi_dbm`, `snr_db` | stored (`rx_packet.rx_rssi`, `rx_snr`) | gateway side only |
| `hop_count` | stored (`rx_packet.hops_taken`) | needs firmware that reports `hopStart` |
| `battery_pct` | stored (`node_metric.battery_pct`) | needs device telemetry enabled |
| `aoi_s` | derivable (`position.gw_rx_ts`) | `kpi.py` computes mean and maximum age per window, not per decision |
| `pdr_5m` | derivable in part | received positions are stored; the number sent needs a vehicle-side log |
| `latency_p95_5m_s` | derivable in part (`logi_event.t_created`, `t_rx_gw`) | only with synchronised clocks |
| `deadline_remaining_s` | derivable (`logi_event.deadline_ts`) | |
| `completed_on_time` (target) | stored (`logi_event.t_done`, `status`, `deadline_ts`) | |
| `external_connectivity` | manual (`outage` table) | the collector does not detect outages |
| `backup_minutes` | not recorded | needs a power measurement |
| `queue_depth` | not recorded | needs a dispatcher-side task list |
| `terminal_available`, `s0_available` | not recorded | need an independent observer, as the protocol requires |

No converter from the collector database to the prototype's CSV format is provided; the feature table has to be
built by a separate, documented preprocessing step.
