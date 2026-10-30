"""End-to-end tests on synthetic data (standard library only):  python -m unittest discover -s tests"""
import json, os, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from logi_proto import LogiMsg, FRAME_LEN, new_event, reply  # noqa: E402
from collector import Collector  # noqa: E402
from import_plan import import_plan  # noqa: E402
from kpi import kpis  # noqa: E402

T0, T1 = 1_800_000_000, 1_800_021_600


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
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        wd = cls.tmp.name
        subprocess.run([sys.executable, str(ROOT / "make_replay.py")], cwd=wd, check=True, capture_output=True,
                       env={**os.environ, "PYTHONPATH": str(ROOT)})
        cls.db_path = os.path.join(wd, "test.db")
        col = Collector(cls.db_path)
        for line in open(os.path.join(wd, "packets.jsonl")):
            rec = json.loads(line)
            pkt = rec["packet"]
            if "payload_hex" in pkt.get("decoded", {}):
                pkt["decoded"]["payload"] = bytes.fromhex(pkt["decoded"].pop("payload_hex"))
            col.handle(pkt, now=rec["t"])
        cls.col = col
        cls.db = sqlite3.connect(cls.db_path)
        import_plan(cls.db, json.load(open(os.path.join(wd, "ops.json"))), 1000)
        cls.k = kpis(cls.db, T0, T1)

    @classmethod
    def tearDownClass(cls):
        cls.db.close(); cls.col.db.close(); cls.tmp.cleanup()

    def test_matches_published_reference(self):
        expected = json.loads((ROOT / "examples" / "expected_kpi_synthetic.json").read_text())
        self.assertEqual(json.loads(json.dumps(self.k)), expected)

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
        self.assertEqual(self.k["eta_actionability"], 0.5)
        self.assertEqual(self.k["A_op"], 0.5)

    def test_every_event_in_outbox(self):
        n = self.db.execute("SELECT COUNT(DISTINCT entity_id) FROM sync_outbox WHERE entity='logi_event'").fetchone()[0]
        self.assertEqual(n, self.k["events"])

    def test_corrupted_frame_is_dropped(self):
        before = self.db.execute("SELECT COUNT(*) FROM logi_event").fetchone()[0]
        raw = bytearray(new_event(999, 6).encode()); raw[3] ^= 1
        with self.assertLogs("collector", "WARNING"):
            self.col.handle({"from": 77, "id": 1, "decoded": {"portnum": 256, "payload": bytes(raw)}}, now=T1 + 10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM logi_event").fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
