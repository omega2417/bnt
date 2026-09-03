"""Metric definitions of sections 14.2 to 14.4, computed from artifacts only.

Every metric takes the same inputs a reviewer would have - the telemetry rows,
the truth records and the alert log - so nothing can be computed from a
privileged internal state that the physical range would not expose.
"""

from __future__ import annotations

from statistics import fmean
from typing import Any, Sequence

from .stats import mean_ci, percentile, wilson_interval

__all__ = ["network_metrics", "power_metrics", "detection_metrics", "summarize"]


def _numbers(rows: Sequence[dict[str, Any]], key: str, site: str | None = None) -> list[float]:
    values = []
    for row in rows:
        if site is not None and row.get("site_id") != site:
            continue
        raw = row.get(key, "")
        if raw in ("", None):
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def network_metrics(rows: Sequence[dict[str, Any]], site: str) -> dict[str, Any]:
    rtt = _numbers(rows, "rtt_ms", site)
    loss = _numbers(rows, "loss_pct", site)
    throughput = _numbers(rows, "throughput_mbps", site)
    offered = _numbers(rows, "offered_load_mbps", site)
    failover = [row for row in rows if row.get("site_id") == site
                and str(row.get("failover_active")) == "1"]
    site_rows = [row for row in rows if row.get("site_id") == site]
    served = sum(1 for row in site_rows if str(row.get("wan_state")) not in ("DOWN", ""))
    return {
        "steps": len(site_rows),
        "availability_pct": round(100.0 * served / len(site_rows), 4) if site_rows else None,
        "rtt_mean_ms": round(fmean(rtt), 4) if rtt else None,
        "rtt_p95_ms": round(percentile(rtt, 0.95), 4) if rtt else None,
        "rtt_p99_ms": round(percentile(rtt, 0.99), 4) if rtt else None,
        "loss_mean_pct": round(fmean(loss), 5) if loss else None,
        "throughput_mean_mbps": round(fmean(throughput), 4) if throughput else None,
        "offered_mean_mbps": round(fmean(offered), 4) if offered else None,
        "goodput_ratio": (round(fmean(throughput) / fmean(offered), 4)
                          if throughput and offered and fmean(offered) > 0 else None),
        "failover_steps": len(failover),
        "failover_seconds": len(failover),
    }


def power_metrics(rows: Sequence[dict[str, Any]], site: str = "site_a") -> dict[str, Any]:
    soc = _numbers(rows, "soc_pct", site)
    autonomy = _numbers(rows, "autonomy_min", site)
    temp = _numbers(rows, "battery_temp_c", site)
    imbalance = _numbers(rows, "cell_imbalance_mv", site)
    site_rows = [row for row in rows if row.get("site_id") == site]
    battery_steps = sum(1 for row in site_rows
                        if str(row.get("power_state_end")) in ("BATTERY", "LOAD_SHED"))
    shed_steps = sum(1 for row in site_rows if str(row.get("shed_groups", "")) not in ("", "0"))
    trips = sum(1 for row in site_rows if str(row.get("protection_trip", "")) != "")
    return {
        "soc_start_pct": round(soc[0], 4) if soc else None,
        "soc_end_pct": round(soc[-1], 4) if soc else None,
        "soc_drop_pct": round(soc[0] - soc[-1], 4) if soc else None,
        "soc_min_pct": round(min(soc), 4) if soc else None,
        "autonomy_min_mean": round(fmean(autonomy), 3) if autonomy else None,
        "autonomy_min_worst": round(min(autonomy), 3) if autonomy else None,
        "battery_steps": battery_steps,
        "load_shed_steps": shed_steps,
        "protection_trip_steps": trips,
        "temp_max_c": round(max(temp), 3) if temp else None,
        "cell_imbalance_max_mv": round(max(imbalance), 3) if imbalance else None,
    }


def detection_metrics(labeled_rows: Sequence[dict[str, Any]],
                      score_key: str = "detector_score",
                      alert_key: str = "detector_alert") -> dict[str, Any]:
    tp = fp = tn = fn = 0
    latencies: list[float] = []
    onset_seen: dict[str, int] = {}
    for row in labeled_rows:
        if row.get("telemetry_gap_marker") in (1, "1"):
            continue
        label = int(row.get("label_attack", 0))
        alert = str(row.get(alert_key, "")) in ("1", "True", "true")
        if label and alert:
            tp += 1
        elif label and not alert:
            fn += 1
        elif not label and alert:
            fp += 1
        else:
            tn += 1
        key = f"{row.get('site_id')}:{row.get('label_truth_ids')}"
        if label and key not in onset_seen:
            onset_seen[key] = int(row.get("step", 0))
        if label and alert and key in onset_seen and f"done:{key}" not in onset_seen:
            latencies.append(int(row.get("step", 0)) - onset_seen[key])
            onset_seen[f"done:{key}"] = 1

    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall and (precision + recall) > 0 else None)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "false_alarm_rate_per_1k_steps": round(1000.0 * fp / max(1, tp + fp + tn + fn), 3),
        "recall_wilson": wilson_interval(tp, tp + fn),
        "detection_latency_steps": mean_ci(latencies),
    }


def summarize(rows: Sequence[dict[str, Any]], labeled: Sequence[dict[str, Any]],
              sites: Sequence[str]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "network": {site: network_metrics(rows, site) for site in sites},
        "power": power_metrics(rows, "site_a"),
        "detection": detection_metrics(labeled),
    }
