"""Indicator calculation from the metadata store.

  python kpi.py --db logi.db --from 1730000000 --to 1730086400

The indicators are the field counterparts of quantities that the accompanying article PREDICTS with a model
(Table 9 of the article lists them with the acceptance criteria fixed in advance). The article itself contains
no measured values, and this program has so far been run only on generated test data. Every result therefore
starts with a "provenance" block; when the data origin is not 'live_radio' or 'recorded_live', the numbers
describe the test generator, not a network.

Definitions (all ratios are returned together with numerator/denominator and a 95 % Wilson interval):

  flood_overhead            duplicate copies / unique packets, as seen through the gateway API
  position_delivery_ratio   positions received / positions expected in the window (not clipped)
  aoi_mean_min              time-average age of the last received position between the first reception and
                            the end of the window, i.e. the silent tail after the last reception is included
  aoi_max_min               largest age reached in that span
  eta_actionability         critical events completed before their deadline / critical events delivered to the
                            gateway (measurement rule of Table 9). It is an operational estimate and an upper
                            bound of the efficacy eta of Equation (4): completing an operation on time does not
                            by itself show that the loss was avoided.
  A_op                      planned critical operations completed by their due time / all planned critical
                            operations in the window (the plan is the denominator and never shrinks)
  on_time_share_loss_weighted   the same share weighted by the assumed loss of each operation. An upper bound of
                            the avoided-loss share q of Equation (4), reached only if eta = 1. It is not a
                            measured loss reduction (in version 1.0.0 it was misleadingly called R_loss).
"""
import argparse, sqlite3, json, math, statistics

CRITICAL_PRIORITY = 3

def wilson(k, n, z=1.96):
    """95 % Wilson score interval for a proportion; None for an empty sample."""
    if not n:
        return None
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(c - h, 0.0), 3), round(min(c + h, 1.0), 3)]

def provenance(db):
    """Data origin of the store. Anything that is not live or recorded radio data is flagged."""
    try:
        rows = db.execute("SELECT data_origin, COUNT(*) FROM collector_session GROUP BY 1").fetchall()
    except sqlite3.OperationalError:
        rows = []
    origins = sorted(o for o, _ in rows)
    origin = origins[0] if len(origins) == 1 else ("mixed" if origins else "unlabelled")
    measured = origin in ("live_radio", "recorded_live")
    note = ("Radio data. Indicators are measurements of this run only; check sample sizes and intervals."
            if measured else
            "NOT A MEASUREMENT. Indicators are computed from generated or unlabelled input and show only that "
            "the software works; they say nothing about the performance of a Meshtastic network.")
    return {"data_origin": origin, "sessions": dict(rows), "is_measurement": measured, "note": note}

def kpis(db, t0, t1, aoi_stale_min=30, position_interval_s=600.0):
    q = lambda sql, *p: db.execute(sql, p).fetchall()
    out = {"provenance": provenance(db), "window_s": [t0, t1], "warnings": []}
    warn = out["warnings"].append
    # Radio (L1). Link quality is averaged over unique packets only; duplicates count as overhead, not delivery.
    r = q("""SELECT COUNT(*), SUM(is_duplicate), AVG(CASE WHEN is_duplicate=0 THEN rx_snr END),
                    AVG(CASE WHEN is_duplicate=0 THEN hops_taken END)
             FROM rx_packet WHERE gw_rx_ts BETWEEN ? AND ?""", t0, t1)[0]
    dup = r[1] or 0
    out["rx_total"], out["rx_duplicates"] = r[0], dup
    out["flood_overhead"] = round(dup / (r[0] - dup), 3) if r[0] - dup else None
    out["snr_mean_db"] = None if r[2] is None else round(r[2], 2)
    out["hops_mean"] = None if r[3] is None else round(r[3], 3)
    # Device state (L2): largest value reported by any node. The collector does not compute these itself.
    u = q("""SELECT MAX(channel_util), MAX(air_util_tx), COUNT(*) FROM node_metric
             WHERE gw_rx_ts BETWEEN ? AND ?""", t0, t1)[0]
    out["channel_util_max_pct"], out["relay_airtime_max_pct"], out["telemetry_records"] = u[0], u[1], u[2]
    if u[2] and u[2] < 6:
        warn(f"channel utilisation rests on {u[2]} telemetry record(s)")
    # Positions: delivery ratio and age of information per node
    exp_n = (t1 - t0) / position_interval_s
    pdr, aoi_mean, aoi_max, stale = {}, {}, {}, []
    for (n,) in q("SELECT DISTINCT node FROM position WHERE gw_rx_ts BETWEEN ? AND ? ORDER BY 1", t0, t1):
        ts = [x[0] for x in q("SELECT gw_rx_ts FROM position WHERE node=? AND gw_rx_ts BETWEEN ? AND ? ORDER BY 1",
                              n, t0, t1)]
        ratio = len(ts) / exp_n if exp_n > 0 else None
        pdr[n] = None if ratio is None else round(ratio, 3)
        if ratio is not None and ratio > 1:
            warn(f"node {n}: more positions than expected; check --position-interval")
        gaps = [b - a for a, b in zip(ts, ts[1:])] + [t1 - ts[-1]]     # last gap = silent tail up to window end
        span = t1 - ts[0]
        if span > 0:
            aoi_mean[n] = round(sum(g * g / 2 for g in gaps) / span / 60, 2)
        aoi_max[n] = round(max(gaps) / 60, 1)
        if max(gaps) / 60 > aoi_stale_min:
            stale.append(n)
    out["position_interval_s"] = position_interval_s
    out["position_delivery_ratio"] = pdr
    out["aoi_mean_min"], out["aoi_max_min"] = aoi_mean, aoi_max
    out["stale_nodes"] = stale          # nodes whose position age exceeded aoi_stale_min at any time in the window
    # Logistics events (L3): latency, acceptance, completion of critical events
    ev = q("""SELECT event_id, t_created, t_rx_gw, t_accept, t_done, deadline_ts, status, priority, deadline_basis
              FROM logi_event WHERE t_rx_gw BETWEEN ? AND ?""", t0, t1)
    crit = [e for e in ev if e[7] == CRITICAL_PRIORITY]
    n = len(crit)
    out["events_total"], out["events_critical"] = len(ev), n
    lat = [e[2] - e[1] for e in ev if e[8] == "sender_clock"]      # meaningful only with synchronised clocks
    out["event_latency_median_s"] = statistics.median(lat) if lat else None
    acc = [e for e in crit if e[3]]
    done_ok = [e for e in crit if e[6] == "DONE" and e[4] is not None and (e[5] is None or e[4] <= e[5])]
    out["accept_ratio"] = round(len(acc) / n, 3) if n else None
    out["eta_actionability"] = round(len(done_ok) / n, 3) if n else None
    out["eta_actionability_n"] = [len(done_ok), n]
    out["eta_actionability_ci95"] = wilson(len(done_ok), n)
    if any(e[8] == "gateway_rx" for e in crit):
        warn("some deadlines start at gateway reception because the sender clock was unset; radio latency is "
             "not counted against those deadlines")
    # Operational autonomy against the plan fixed in advance
    plan = q("""SELECT p.operation_id, p.due_ts, p.loss_if_failed,
                       (SELECT MIN(t_done) FROM logi_event e WHERE e.operation_id=p.operation_id AND e.status='DONE')
                FROM planned_operation p WHERE p.critical=1 AND p.due_ts BETWEEN ? AND ?""", t0, t1)
    ok = [p for p in plan if p[3] is not None and p[3] <= p[1]]
    out["A_op"] = round(len(ok) / len(plan), 3) if plan else None        # undefined for an empty plan
    out["A_op_n"] = [len(ok), len(plan)]
    out["A_op_ci95"] = wilson(len(ok), len(plan))
    base = sum(p[2] or 0 for p in plan)
    out["on_time_share_loss_weighted"] = round(sum(p[2] or 0 for p in ok) / base, 3) if base else None
    if plan and len(plan) < 30:
        warn(f"A_op rests on {len(plan)} planned operations; see the confidence interval")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", default="logi.db"); ap.add_argument("--from", dest="t0", type=float, required=True)
    ap.add_argument("--to", dest="t1", type=float, required=True)
    ap.add_argument("--position-interval", type=float, default=600.0, help="configured position interval, s")
    ap.add_argument("--stale-min", type=float, default=30.0, help="position age that counts as stale, min")
    a = ap.parse_args()
    print(json.dumps(kpis(sqlite3.connect(a.db), a.t0, a.t1, a.stale_min, a.position_interval), indent=1))
