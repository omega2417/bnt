"""The five automated verifications of Table 4."""
import json
import tempfile
import unittest
from pathlib import Path

from metatwin_guard import benchmark
from metatwin_guard.events import tamper_features

from helpers import fitted_guard, make_sensor, make_stream


class TestCoreInvariants(unittest.TestCase):
    def test_clean_stream_accepted_and_state_updated(self):
        s = make_sensor()
        guard = fitted_guard(s, 30)
        self.assertEqual(guard.twin.version, 30)
        ev = make_stream(s, 1, "evaluation", seed=99, start=100)[0]
        rec = guard.process(ev)
        self.assertTrue(rec["admitted"], rec["reasons"])
        self.assertTrue(rec["state_changed"])
        self.assertEqual(guard.twin.nodes[s.topology_node]["event_id"], ev["event_id"])

    def test_replay_rejected_state_unchanged_evidence_retained(self):
        s = make_sensor()
        guard = fitted_guard(s, 30)
        old = make_stream(make_sensor(), 30)[5]  # same keys/seed -> identical 6th event
        before = guard.twin.state_hash()
        n_blocks = len(guard.ledger.blocks)
        rec = guard.process(old)
        self.assertFalse(rec["admitted"])
        self.assertIn("duplicate_event_id", rec["reasons"])
        self.assertIn("non_increasing_sequence", rec["reasons"])
        self.assertTrue(rec["hybrid_alert"])
        self.assertEqual(guard.twin.state_hash(), before)
        self.assertEqual(len(guard.ledger.blocks), n_blocks + 1)
        self.assertFalse(guard.ledger.blocks[-1]["body"]["integrity_admitted"])

    def test_post_signature_tamper_rejected(self):
        for fix_hash, reason in ((False, "payload_hash_mismatch"), (True, "signature_invalid")):
            s = make_sensor()
            guard = fitted_guard(s, 30)
            ev = make_stream(s, 1, "evaluation", seed=3, start=100)[0]
            bad = tamper_features(ev, {"rtt_ms": 999.0}, fix_payload_hash=fix_hash)
            before = guard.twin.state_hash()
            rec = guard.process(bad)
            self.assertFalse(rec["admitted"])
            self.assertIn(reason, rec["reasons"])
            self.assertEqual(guard.twin.state_hash(), before)
            # the untampered original is still admissible afterwards
            self.assertTrue(guard.process(ev)["admitted"])

    def test_evidence_block_tampering_detected(self):
        s = make_sensor()
        guard = fitted_guard(s, 20)
        self.assertTrue(guard.ledger.verify().valid)
        forged = guard.ledger.tampered_copy()
        forged.blocks[7]["body"]["hybrid_alert"] = not forged.blocks[7]["body"]["hybrid_alert"]
        rep = forged.verify()
        self.assertFalse(rep.valid)
        self.assertTrue(any(e.startswith("block 7") for e in rep.errors))
        self.assertTrue(guard.ledger.verify().valid)  # original untouched

    def test_benchmark_outputs_and_ledger_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            rc = benchmark.main(["--reps", "1", "--out", d, "--quiet"])
            self.assertEqual(rc, 0)
            for f in ("run_level.csv", "summary.csv", "ablation_executed.csv", "metadata.json"):
                self.assertTrue((Path(d) / f).exists(), f)
            meta = json.loads((Path(d) / "metadata.json").read_text())
            self.assertTrue(meta["all_ledgers_valid"])
            self.assertEqual(meta["n_events"], 6 * 360)


if __name__ == "__main__":
    unittest.main()
