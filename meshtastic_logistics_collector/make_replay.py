"""Generated replay log for testing the collector without radio hardware.

EVERYTHING WRITTEN BY THIS SCRIPT IS INVENTED TEST INPUT, NOT A MEASUREMENT.
No radio was involved. All "radio" values are either drawn from a pseudo-random generator with a fixed seed
or typed in by hand as constants:

  * 3 vehicles (nodes 11-13) report a position every 10 min for 6 h; each report is dropped with a
    probability of 0.15 that was chosen by hand, and 30 % of the kept ones get one duplicate copy;
  * SNR is uniform in [-12, 8] dB and RSSI uniform in [-120, -80] dBm, with no propagation model behind them;
  * one telemetry record of relay 21 carries channelUtilization = 4.2 % and airUtilTx = 1.3 %. These two
    numbers are hand-set constants chosen close to the article's model predictions (3.92 % and 1.31 %).
    Reading them back from the database therefore confirms nothing about the model or about a real channel;
  * 4 critical events with a 30-min deadline whose outcomes are scripted: two completed on time, one
    completed late, one never completed. Every indicator derived from them (eta = A_op = 0.5) is fixed
    by this script and carries no information about a real operation.

Output: packets.jsonl (input for `collector.py --replay`; its first line is a meta record that declares
data_origin = "synthetic") and ops.json (planned operations for import_plan.py).
Compared with version 1.0.0 the packet stream is unchanged except for two things: the meta line is new, and
ACCEPT/DONE frames now carry a timestamp from the scenario clock (1.0.0 took it from the wall clock, so its
output was not bit-reproducible, contrary to what its changelog said).
"""
import argparse, json, random
from pathlib import Path
from logi_proto import new_event, reply

T0 = 1_800_000_000                  # arbitrary start of the 6-hour window (unix s)
P_KEEP_POSITION = 0.85              # hand-set, not measured
P_DUPLICATE = 0.30                  # hand-set, not measured
TELEMETRY = {"batteryLevel": 87, "voltage": 4.01, "channelUtilization": 4.2, "airUtilTx": 1.3,
             "uptimeSeconds": 3600}  # hand-set constants, see module docstring
META = {"data_origin": "synthetic", "generator": "make_replay.py", "seed": [1, 42],
        "warning": "Invented test input. Not a measurement of any radio network."}

def generate():
    rnd = random.Random(1)          # packet stream
    rid = random.Random(42)         # event ids (separate generator, so that ids do not shift the stream)
    out, state = [], {"pid": 1000}

    def pk(t, frm, port, dec, hops=1, dup=False):
        if not dup:
            state["pid"] += 1
        out.append({"t": t, "packet": {
            "from": frm, "to": 4294967295, "id": state["pid"],
            "rxSnr": round(rnd.uniform(-12, 8), 1), "rxRssi": rnd.randint(-120, -80),
            "hopLimit": 3 - hops, "hopStart": 3, "rxTime": int(t), "decoded": dict(portnum=port, **dec)}})

    for v in (11, 12, 13):
        for k in range(36):
            t = T0 + k * 600 + v
            if rnd.random() < P_KEEP_POSITION:
                hops = rnd.choice([1, 2])
                pk(t, v, "POSITION_APP", {"position": {"latitudeI": 484500000 + k * 100, "longitudeI": 350400000,
                                                       "satsInView": 9, "time": int(t)}}, hops=hops)
                if rnd.random() < P_DUPLICATE:
                    pk(t + 2, v, "POSITION_APP", {"position": {"latitudeI": 1, "longitudeI": 1}}, dup=True)
    pk(T0 + 50, 21, "TELEMETRY_APP", {"telemetry": {"deviceMetrics": TELEMETRY}})

    ops = []
    for i, op in enumerate([501, 502, 503, 504]):
        ev = new_event(op, 1, value=85, deadline_min=30)
        ev.t_created = T0 + 1000 * i + 100
        ev.event_id = bytes(rid.getrandbits(8) for _ in range(6))
        pk(T0 + 1000 * i + 101, 11, 256, {"payload_hex": ev.encode().hex()}, hops=2)
        pk(T0 + 1000 * i + 160, 1, 256, {"payload_hex": _at(reply(ev, 2), T0 + 1000 * i + 160).encode().hex()})
        if i < 3:                   # scripted outcome: events 0 and 1 on time, 2 late, 3 never completed
            t_done = T0 + 1000 * i + (900 if i < 2 else 2500)
            pk(t_done, 11, 256, {"payload_hex": _at(reply(ev, 3), t_done).encode().hex()}, hops=2)
        ops.append((op, T0 + 1000 * i + 100 + 1800))
    return out, ops

def _at(msg, t):
    """Give a reply a timestamp from the scenario clock instead of the wall clock (bit-reproducible output)."""
    msg.t_created = t
    return msg

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Write an invented replay log (synthetic test input, not measurements)")
    ap.add_argument("--out-dir", default=".")
    a = ap.parse_args()
    packets, ops = generate()
    d = Path(a.out_dir); d.mkdir(parents=True, exist_ok=True)
    (d / "ops.json").write_text(json.dumps(ops))
    with open(d / "packets.jsonl", "w") as f:
        f.write(json.dumps({"meta": META}) + "\n")
        for r in packets:
            f.write(json.dumps(r) + "\n")
    print(len(packets))
