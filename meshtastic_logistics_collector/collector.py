"""Metadata collector for a Meshtastic logistics gateway.

Runs on the local gateway (mini-PC / Raspberry Pi) connected to a Meshtastic node by USB or TCP.
Works without Internet; writes everything to a local SQLite database.

  python collector.py --serial /dev/ttyUSB0 --db logi.db
  python collector.py --tcp 192.168.1.50 --db logi.db
  python collector.py --replay packets.jsonl --db test.db     # offline test without a radio

Tested with meshtastic-python 2.7.11 (API: SerialInterface/TCPInterface, pubsub topic "meshtastic.receive",
MeshInterface.sendData(..., portNum=256, wantAck=True)).
"""
import argparse, json, sqlite3, time, logging
from pathlib import Path
from logi_proto import LogiMsg, MSG_TYPES

PRIVATE_APP = 256
DUP_WINDOW_S = 600
log = logging.getLogger("collector")

def _portnum(dec):
    p = dec.get("portnum")
    return {256: "PRIVATE_APP"}.get(p, str(p)) if p is not None else None

class Collector:
    def __init__(self, db_path, iface=None):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.executescript(Path(__file__).with_name("schema.sql").read_text())
        self.iface = iface          # needed only to send ACK replies

    # ---------- generic radio metadata (L1) ----------
    def handle(self, pkt, now=None):
        now = now or time.time()
        dec = pkt.get("decoded", {}) or {}
        frm = pkt.get("from"); pid = pkt.get("id")
        hl, hs = pkt.get("hopLimit"), pkt.get("hopStart")
        hops = (hs - hl) if (hs is not None and hl is not None) else None
        dup = self.db.execute("SELECT 1 FROM rx_packet WHERE from_node=? AND pkt_id=? AND gw_rx_ts>?",
                              (frm, pid, now - DUP_WINDOW_S)).fetchone() is not None
        payload = dec.get("payload") or b""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO rx_packet(gw_rx_ts,pkt_id,from_node,to_node,channel,portnum,rx_time,rx_snr,rx_rssi,"
            "hop_limit,hop_start,hops_taken,via_mqtt,payload_len,is_duplicate) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, pid, frm, pkt.get("to"), pkt.get("channel", 0), _portnum(dec), pkt.get("rxTime"), pkt.get("rxSnr"),
             pkt.get("rxRssi"), hl, hs, hops, int(bool(pkt.get("viaMqtt"))), len(payload), int(dup)))
        rx_id = cur.lastrowid
        self.db.execute("INSERT INTO node_registry(node,first_seen,last_seen) VALUES(?,?,?) "
                        "ON CONFLICT(node) DO UPDATE SET last_seen=excluded.last_seen", (frm, now, now))
        if not dup:
            port = _portnum(dec)
            if port == "TELEMETRY_APP":
                self._telemetry(frm, dec.get("telemetry", {}), now)
            elif port == "POSITION_APP":
                self._position(frm, dec.get("position", {}), pkt, hops, now)
            elif port == "PRIVATE_APP" and payload:
                self._logistics(frm, bytes(payload), hops, rx_id, now)
            elif port == "NODEINFO_APP":
                self._nodeinfo(frm, dec.get("user", {}))
        self.db.commit()

    # ---------- L2: device state ----------
    def _telemetry(self, node, tel, now):
        dm, em = tel.get("deviceMetrics", {}), tel.get("environmentMetrics", {})
        if not dm and not em:
            return
        self.db.execute("INSERT OR REPLACE INTO node_metric VALUES(?,?,?,?,?,?,?,?)",
                        (node, now, dm.get("batteryLevel"), dm.get("voltage"), dm.get("channelUtilization"),
                         dm.get("airUtilTx"), dm.get("uptimeSeconds"), em.get("temperature")))

    def _position(self, node, pos, pkt, hops, now):
        lat = pos.get("latitude", (pos.get("latitudeI") or 0) * 1e-7 or None)
        lon = pos.get("longitude", (pos.get("longitudeI") or 0) * 1e-7 or None)
        self.db.execute("INSERT OR REPLACE INTO position VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (node, now, lat, lon, pos.get("altitude"), pos.get("time"), pos.get("satsInView"),
                         pos.get("precisionBits"), pkt.get("rxSnr"), hops))

    def _nodeinfo(self, node, user):
        self.db.execute("UPDATE node_registry SET node_id=?, long_name=?, short_name=?, hw_model=?, role=COALESCE(?,role) "
                        "WHERE node=?", (user.get("id"), user.get("longName"), user.get("shortName"),
                                         str(user.get("hwModel")), user.get("role"), node))

    # ---------- L3: logistics events ----------
    def _logistics(self, node, raw, hops, rx_id, now):
        try:
            m = LogiMsg.decode(raw)
        except ValueError as e:
            log.warning("bad logistics frame from %s: %s", node, e); return
        eid = m.event_hex
        self.db.execute("INSERT INTO logi_event_log(event_id,msg_type,from_node,gw_rx_ts,rx_id) VALUES(?,?,?,?,?)",
                        (eid, m.msg_type, node, now, rx_id))
        if m.msg_type == 1:  # EVENT
            dl = (now + 60 * m.deadline_min) if m.deadline_min else None
            self.db.execute("INSERT OR IGNORE INTO logi_event(event_id,operation_id,origin_node,event_code,priority,"
                            "t_created,t_rx_gw,hops_taken,value,deadline_ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (eid, m.operation_id, node, m.event_code, m.priority, m.t_created, now, hops, m.value, dl))
            self._outbox("logi_event", eid, {"op": m.operation_id, "code": m.event_code, "value": m.value}, now)
        elif m.msg_type in (2, 3, 4):
            col, st = {2: ("t_accept", "ACCEPTED"), 3: ("t_done", "DONE"), 4: ("t_done", "REJECTED")}[m.msg_type]
            self.db.execute(f"UPDATE logi_event SET {col}=COALESCE({col},?), status=? WHERE event_id=?", (now, st, eid))
            self._outbox("logi_event_state", eid, {"state": st}, now)

    def _outbox(self, entity, eid, data, now):
        self.db.execute("INSERT INTO sync_outbox(entity,entity_id,payload_json,created_ts) VALUES(?,?,?,?)",
                        (entity, eid, json.dumps(data), now))

    # ---------- dispatcher side: send ACCEPT/DONE back over the mesh ----------
    def send(self, msg: LogiMsg, dest="^all", channel_index=1):
        if self.iface is None:
            raise RuntimeError("no radio interface")
        self.iface.sendData(msg.encode(), destinationId=dest, portNum=PRIVATE_APP, wantAck=True,
                            channelIndex=channel_index)

def run_radio(args):
    from pubsub import pub
    import meshtastic.serial_interface, meshtastic.tcp_interface
    iface = (meshtastic.tcp_interface.TCPInterface(hostname=args.tcp) if args.tcp
             else meshtastic.serial_interface.SerialInterface(devPath=args.serial))
    col = Collector(args.db, iface)
    pub.subscribe(lambda packet, interface: col.handle(packet), "meshtastic.receive")
    log.info("collector running; Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    finally:
        iface.close()

def run_replay(args):
    col = Collector(args.db)
    for line in open(args.replay):
        rec = json.loads(line)
        pkt = rec["packet"]
        if "payload_hex" in pkt.get("decoded", {}):
            pkt["decoded"]["payload"] = bytes.fromhex(pkt["decoded"].pop("payload_hex"))
        col.handle(pkt, now=rec["t"])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial"); ap.add_argument("--tcp"); ap.add_argument("--replay")
    ap.add_argument("--db", default="logi.db")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    run_replay(a) if a.replay else run_radio(a)
