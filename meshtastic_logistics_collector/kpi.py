"""KPI calculation from the metadata store (links the field data to the paper's model).

  python kpi.py --db logi.db --from 1730000000 --to 1730086400
"""
import argparse, sqlite3, json, math

def kpis(db, t0, t1, aoi_stale_min=30):
    q = lambda sql, *p: db.execute(sql, p).fetchall()
    out = {}
    # Radio: delivery of unique packets per source, hops, link quality
    r = q("""SELECT COUNT(*), SUM(is_duplicate), AVG(rx_snr), AVG(hops_taken)
             FROM rx_packet WHERE gw_rx_ts BETWEEN ? AND ?""", t0, t1)[0]
    out["rx_total"], out["rx_duplicates"] = r[0], r[1] or 0
    out["flood_overhead"] = round((r[1] or 0) / max(r[0] - (r[1] or 0), 1), 3)   # rebroadcast copies per unique packet
    out["snr_mean_db"], out["hops_mean"] = r[2], r[3]
    # Channel utilization U as reported by nodes (mean of max per node)
    u = q("""SELECT node, MAX(channel_util), MAX(air_util_tx) FROM node_metric
             WHERE gw_rx_ts BETWEEN ? AND ? GROUP BY node""", t0, t1)
    out["channel_util_max_pct"] = max([x[1] or 0 for x in u], default=None)
    out["relay_airtime_max_pct"] = max([x[2] or 0 for x in u], default=None)
    # Position delivery ratio p (expected reports per vehicle vs received) and age of information
    pos = q("""SELECT node, COUNT(*), MAX(gw_rx_ts) FROM position WHERE gw_rx_ts BETWEEN ? AND ? GROUP BY node""", t0, t1)
    interval = 600.0
    exp_n = max((t1 - t0) / interval, 1)
    out["position_delivery_ratio"] = {n: round(min(c / exp_n, 1.0), 3) for n, c, _ in pos}
    out["stale_nodes"] = [n for n, _, last in pos if (t1 - last) / 60 > aoi_stale_min]
    # AoI: time-average age from consecutive receptions
    aoi = {}
    for n, *_ in pos:
        ts = [x[0] for x in q("SELECT gw_rx_ts FROM position WHERE node=? AND gw_rx_ts BETWEEN ? AND ? ORDER BY 1", n, t0, t1)]
        if len(ts) >= 2:
            area = sum((b - a) ** 2 / 2 for a, b in zip(ts, ts[1:]))
            aoi[n] = round(area / (ts[-1] - ts[0]) / 60, 2)
    out["aoi_mean_min"] = aoi
    # Logistics events: latency, acceptance, completion
    ev = q("""SELECT event_id, t_created, t_rx_gw, t_accept, t_done, deadline_ts, status FROM logi_event
              WHERE t_rx_gw BETWEEN ? AND ?""", t0, t1)
    n = len(ev)
    lat = [e[2] - e[1] for e in ev if e[1]]
    out["events"] = n
    out["event_latency_median_s"] = sorted(lat)[len(lat) // 2] if lat else None
    acc = [e for e in ev if e[3]]
    done_ok = [e for e in ev if e[4] and (e[5] is None or e[4] <= e[5]) and e[6] == "DONE"]
    out["accept_ratio"] = round(len(acc) / n, 3) if n else None
    # eta = completed on time / delivered critical messages  (Equation (9) of the paper)
    out["eta_actionability"] = round(len(done_ok) / n, 3) if n else None
    # A_op = critical planned operations completed on time / all planned in window (denominator never shrinks)
    plan = q("""SELECT p.operation_id, p.due_ts, p.loss_if_failed_uah,
                       (SELECT MIN(t_done) FROM logi_event e WHERE e.operation_id=p.operation_id AND e.status='DONE')
                FROM planned_operation p WHERE p.critical=1 AND p.due_ts BETWEEN ? AND ?""", t0, t1)
    if plan:
        ok = [p for p in plan if p[3] is not None and p[3] <= p[1]]
        out["A_op"] = round(len(ok) / len(plan), 3)
        base = sum(p[2] or 0 for p in plan)
        out["R_loss"] = round(sum(p[2] or 0 for p in ok) / base, 3) if base else None
    else:
        out["A_op"] = None  # undefined: zero denominator
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="logi.db"); ap.add_argument("--from", dest="t0", type=float, required=True)
    ap.add_argument("--to", dest="t1", type=float, required=True)
    a = ap.parse_args()
    print(json.dumps(kpis(sqlite3.connect(a.db), a.t0, a.t1), indent=1, default=str))
