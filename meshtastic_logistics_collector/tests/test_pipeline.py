"""End-to-end software tests on generated input (standard library only):  python -m unittest discover -s tests

These tests establish that the code does what it documents on scripted input. They establish nothing about
radio hardware, firmware compatibility or the performance of a real network.
"""
import json, os, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logi_proto import LogiMsg, FRAME_LEN, new_event, reply  # noqa: E402
from collector import Collector, read_replay  # noqa: E402
from import_plan import import_plan  # noqa: E402
from kpi import kpis, wilson  # noqa: E402

T0, T1 = 1_800_000_000, 1_800_021_600


def pkt(frm, pid, port, **dec):
    return {"from": frm, "id": pid, "hopLimit": 2, "hopStart": 3, "decoded": dict(portnum=port, **dec)}


class ProtocolTest(unittest.TestCase):
    def test_roundtrip(self):
        ev = new_event(501, 1, value=-85, deadline_min=30)
        raw = ev.encode()
        self.assertEqual(len(raw), FRAME_LEN)
        self.assertEqual(LogiMsg.decode(raw), ev)

    def test_reply_keeps_event_id(self):
        ev = new_event(501, 1)
        self.assertEqual(reply(ev, 3).event_id, ev.event_id)

    def test_corrupted_frame_rejected(self):
        raw = bytearray(new_event(501, 1).encode())
        raw[5] ^= 0xFF
        with self.assertRaises(ValueError):
            LogiMsg.decode(bytes(raw))
        with self.assertRaises(ValueError):
            LogiMsg.decode(bytes(raw[:-1]))


class PipelineTest(unittest.TestCase):
    """Replays the generated log of make_replay.py through the collector."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        wd = cls.tmp.name
        subprocess.run([sys.executable, str(ROOT / "make_replay.py"), "--out-dir", wd], check=True,
                       capture_output=True, env={**os.environ, "PYTHONPATH": str(ROOT)})
        cls.wd = wd
        cls.db_path = os.path.join(wd, "test.db")
        meta, recs = read_replay(os.path.join(wd, "packets.jsonl"))
        cls.meta = meta
        col = Collector(cls.db_path, source="replay", data_origin=meta["data_origin"])
        for rec in recs:
            col.handle(rec["packet"], now=rec["t"])
        cls.col = col
        cls.db = sqlite3.connect(cls.db_path)
        import_plan(cls.db, json.loads(Path(wd, "ops.json").read_text()), 1000)
        cls.k = kpis(cls.db, T0, T1)

    @classmethod
    def tearDownClass(cls):
        cls.db.close(); cls.col.db.close(); cls.tmp.cleanup()

    def test_matches_reference_output(self):
        """Determinism check: same code + same seed -> same numbers. Not a validation of the numbers."""
        expected = json.loads((ROOT / "examples" / "expected_kpi_synthetic.json").read_text())
        self.assertEqual(json.loads(json.dumps(self.k)), expected)

    def test_generator_is_bit_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, str(ROOT / "make_replay.py"), "--out-dir", d], check=True,
                           capture_output=True, env={**os.environ, "PYTHONPATH": str(ROOT)})
            self.assertEqual(Path(d, "packets.jsonl").read_bytes(), Path(self.wd, "packets.jsonl").read_bytes())

    def test_synthetic_origin_is_reported(self):
        self.assertEqual(self.meta["data_origin"], "synthetic")
        p = self.k["provenance"]
        self.assertEqual(p["data_origin"], "synthetic")
        self.assertIs(p["is_measurement"], False)
        self.assertIn("NOT A MEASUREMENT", p["note"])

    def test_duplicates_separated_from_delivery(self):
        n_pos = self.db.execute("SELECT COUNT(*) FROM position").fetchone()[0]
        n_dup = self.db.execute("SELECT COUNT(*) FROM rx_packet WHERE is_duplicate=1").fetchone()[0]
        self.assertEqual(n_dup, self.k["rx_duplicates"])
        self.assertEqual(n_pos, self.db.execute(
            "SELECT COUNT(*) FROM rx_packet WHERE portnum='POSITION_APP' AND is_duplicate=0").fetchone()[0])

    def test_event_life_cycle(self):
        st = sorted(r[0] for r in self.db.execute("SELECT status FROM logi_event"))
        self.assertEqual(st, ["ACCEPTED", "DONE", "DONE", "DONE"])

    def test_late_completion_not_counted(self):
        self.assertEqual(self.k["eta_actionability_n"], [2, 4])
        self.assertEqual(self.k["A_op_n"], [2, 4])
        self.assertEqual(self.k["A_op"], 0.5)

    def test_small_sample_is_flagged(self):
        lo, hi = self.k["A_op_ci95"]
        self.assertLess(lo, 0.2); self.assertGreater(hi, 0.8)       # 2 of 4 says almost nothing
        self.assertTrue(any("planned operations" in w for w in self.k["warnings"]))

    def test_silent_tail_counts_as_stale(self):
        """A node whose position aged beyond the threshold inside the window is reported (1.0.0 missed it)."""
        self.assertIn(13, self.k["stale_nodes"])
        self.assertEqual(self.k["aoi_max_min"][13], 40.0)

    def test_every_event_in_outbox(self):
        n = self.db.execute("SELECT COUNT(DISTINCT entity_id) FROM sync_outbox WHERE entity='logi_event'").fetchone()[0]
        self.assertEqual(n, self.k["events_total"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sync_outbox WHERE sent_ts IS NOT NULL").fetchone()[0], 0)

    def test_corrupted_frame_is_dropped(self):
        before = self.db.execute("SELECT COUNT(*) FROM logi_event").fetchone()[0]
        raw = bytearray(new_event(999, 6).encode()); raw[3] ^= 1
        with self.assertLogs("collector", "WARNING"):
            self.col.handle({"from": 77, "id": 1, "decoded": {"portnum": 256, "payload": bytes(raw)}}, now=T1 + 10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM logi_event").fetchone()[0], before)


class RulesTest(unittest.TestCase):
    """Accounting rules that keep the indicators from being flattered."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.db")

    def tearDown(self):
        self.tmp.cleanup()

    def _event(self, col, t_created, t_rx, deadline_min=30, op=1):
        ev = new_event(op, 1, deadline_min=deadline_min); ev.t_created = t_created
        col.handle(pkt(11, 1, 256, payload=ev.encode()), now=t_rx)
        return ev

    def test_unlabelled_data_is_not_a_measurement(self):
        col = Collector(self.path)                                   # origin not declared
        col.handle(pkt(11, 1, "POSITION_APP", position={"latitudeI": 1, "longitudeI": 1}), now=T0 + 1)
        p = kpis(col.db, T0, T1)["provenance"]
        self.assertEqual(p["data_origin"], "unlabelled"); self.assertIs(p["is_measurement"], False)
        with self.assertRaises(ValueError):
            Collector(self.path, data_origin="measured")             # only the declared vocabulary is accepted

    def test_mixed_origins_are_reported(self):
        Collector(self.path, data_origin="synthetic").db.close()
        col = Collector(self.path, data_origin="live_radio")
        p = kpis(col.db, T0, T1)["provenance"]
        self.assertEqual(p["data_origin"], "mixed"); self.assertIs(p["is_measurement"], False)

    def test_replay_cannot_claim_live_radio(self):
        f = os.path.join(self.tmp.name, "r.jsonl")
        with open(f, "w") as fh:
            fh.write(json.dumps({"meta": {"data_origin": "live_radio"}}) + "\n")
            fh.write(json.dumps({"t": T0 + 1, "packet": pkt(11, 1, "POSITION_APP", position={})}) + "\n")
        r = subprocess.run([sys.executable, str(ROOT / "collector.py"), "--replay", f, "--db", self.path],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        db = sqlite3.connect(self.path)
        self.assertEqual(db.execute("SELECT data_origin FROM collector_session").fetchall(), [("unlabelled",)])
        db.close()

    def test_radio_latency_counts_against_deadline(self):
        col = Collector(self.path)
        ev = self._event(col, T0, T0 + 1500)                         # frame needed 25 min to reach the gateway
        d = reply(ev, 3); col.handle(pkt(11, 2, 256, payload=d.encode()), now=T0 + 2000)   # done 33 min after creation
        row = col.db.execute("SELECT deadline_ts, deadline_basis FROM logi_event").fetchone()
        self.assertEqual(row, (T0 + 1800, "sender_clock"))
        self.assertEqual(kpis(col.db, T0, T1)["eta_actionability_n"], [0, 1])

    def test_unset_sender_clock_falls_back_and_warns(self):
        col = Collector(self.path)
        self._event(col, 0, T0 + 100)
        self.assertEqual(col.db.execute("SELECT deadline_basis FROM logi_event").fetchone()[0], "gateway_rx")
        k = kpis(col.db, T0, T1)
        self.assertTrue(any("sender clock" in w for w in k["warnings"]))
        self.assertIsNone(k["event_latency_median_s"])

    def test_late_accept_does_not_reopen_done_event(self):
        col = Collector(self.path)
        ev = self._event(col, T0, T0 + 1)
        col.handle(pkt(11, 2, 256, payload=reply(ev, 3).encode()), now=T0 + 600)
        col.handle(pkt(1, 3, 256, payload=reply(ev, 2).encode()), now=T0 + 700)
        col.handle(pkt(11, 4, 256, payload=reply(ev, 4).encode()), now=T0 + 800)       # REJECT after DONE
        self.assertEqual(col.db.execute("SELECT status, t_done FROM logi_event").fetchone(), ("DONE", T0 + 600))

    def test_reply_to_unknown_event_is_logged_not_counted(self):
        col = Collector(self.path)
        ghost = new_event(7, 1)
        with self.assertLogs("collector", "WARNING"):
            col.handle(pkt(11, 1, 256, payload=reply(ghost, 3).encode()), now=T0 + 5)
        self.assertEqual(col.db.execute("SELECT COUNT(*) FROM logi_event").fetchone()[0], 0)
        self.assertEqual(col.db.execute("SELECT COUNT(*) FROM logi_event_log").fetchone()[0], 1)

    def test_unsupported_operation_stays_in_denominator(self):
        col = Collector(self.path)
        import_plan(col.db, [[1, T0 + 1800], [2, T0 + 1800]], 100)   # operation 2 never produces a message
        ev = self._event(col, T0, T0 + 1, op=1)
        col.handle(pkt(11, 2, 256, payload=reply(ev, 3).encode()), now=T0 + 600)
        k = kpis(col.db, T0, T1)
        self.assertEqual(k["A_op_n"], [1, 2]); self.assertEqual(k["on_time_share_loss_weighted"], 0.5)

    def test_empty_plan_is_undefined_not_zero(self):
        k = kpis(Collector(self.path).db, T0, T1)
        self.assertIsNone(k["A_op"]); self.assertIsNone(k["A_op_ci95"]); self.assertIsNone(k["flood_overhead"])

    def test_delivery_ratio_is_not_clipped(self):
        col = Collector(self.path)
        for i in range(8):
            col.handle(pkt(11, i, "POSITION_APP", position={"latitudeI": 1, "longitudeI": 1}), now=T0 + 300 * i)
        k = kpis(col.db, T0, T0 + 2400, position_interval_s=600)
        self.assertEqual(k["position_delivery_ratio"][11], 2.0)
        self.assertTrue(any("more positions than expected" in w for w in k["warnings"]))

    def test_wilson_interval(self):
        self.assertIsNone(wilson(0, 0))
        self.assertEqual(wilson(2, 4), [0.15, 0.85])


if __name__ == "__main__":
    unittest.main()
