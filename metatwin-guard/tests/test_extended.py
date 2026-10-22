"""Part of the extended verification suite (Section 4.4 gate): edge cases
that the five core tests do not exercise."""
import math
import unittest
from datetime import timedelta

from metatwin_guard import QuorumEvidenceLedger, RobustDetector
from metatwin_guard.crypto import deterministic_private_key, sign_hex
from metatwin_guard.detector import min_simultaneous_deviations
from metatwin_guard.generator import generate_run

from helpers import T0, fitted_guard, make_sensor, make_stream


class TestGatewayEdgeCases(unittest.TestCase):
    def test_unknown_sensor_rejected(self):
        guard = fitted_guard(make_sensor(), 10)
        stranger = make_sensor("s-unknown")
        rec = guard.process(make_stream(stranger, 1)[0])
        self.assertFalse(rec["admitted"])
        self.assertIn("unknown_sensor_key", rec["reasons"])

    def test_wrong_key_signature_rejected(self):
        s = make_sensor()
        guard = fitted_guard(s, 10)
        imposter = make_sensor(s.sensor_id, seed=2)  # same id, different key
        imposter.seq, imposter.last_hash = s.seq, s.last_hash
        rec = guard.process(make_stream(imposter, 1, start=50)[0])
        self.assertIn("signature_invalid", rec["reasons"])

    def test_malformed_events_rejected_without_crash(self):
        s = make_sensor()
        guard = fitted_guard(s, 10)
        ev = make_stream(s, 1, start=50)[0]
        for mutate in (
            lambda e: e.pop("signature"),
            lambda e: e.__setitem__("source_seq", "11"),
            lambda e: e.__setitem__("source_seq", True),
            lambda e: e["features"].__setitem__("rtt_ms", float("nan")),
            lambda e: e["features"].pop("power_status"),
            lambda e: e.__setitem__("event_time_utc", "yesterday"),
        ):
            bad = {**ev, "features": dict(ev["features"])}
            mutate(bad)
            rec = guard.process(bad)
            self.assertFalse(rec["admitted"])
            self.assertTrue(rec["reasons"][0].startswith("schema:"))
        self.assertFalse(guard.process("not an event")["admitted"])
        self.assertTrue(guard.process(ev)["admitted"])

    def test_cross_source_id_collision_rejected(self):
        a, b = make_sensor("s-a"), make_sensor("s-b")
        from metatwin_guard import MetaTwinGuard
        guard = MetaTwinGuard({x.sensor_id: x.private_key.public_key() for x in (a, b)})
        ea = make_stream(a, 1)[0]
        self.assertTrue(guard.process(ea)["admitted"])
        b.emit({**ea["features"]}, T0, 1.0, "test", "baseline")  # advance b
        eb = make_stream(b, 1)[0]
        eb["event_id"] = ea["event_id"]  # collision (signature now also breaks)
        rec = guard.process(eb)
        self.assertIn("duplicate_event_id", rec["reasons"])

    def test_delayed_valid_event_admitted_but_stale(self):
        s = make_sensor()
        guard = fitted_guard(s, 5)
        late = s.emit(guard.twin.nodes[s.topology_node]["features"], T0 - timedelta(minutes=10), 45.0, "test", "evaluation")
        self.assertTrue(guard.process(late)["admitted"])
        now = T0 + timedelta(seconds=10)
        self.assertEqual(guard.twin.freshness(s.topology_node, now), "unknown")
        self.assertEqual(guard.twin.freshness("never-seen", now), "unknown")

    def test_out_of_order_delivery_rejected(self):
        s = make_sensor()
        guard = fitted_guard(s, 5)
        e1, e2 = make_stream(s, 2, start=20)
        self.assertTrue(guard.process(e2)["admitted"] is False)  # gap in chain
        self.assertTrue(guard.process(e1)["admitted"])


class TestLedgerQuorum(unittest.TestCase):
    def _ledger(self):
        led = QuorumEvidenceLedger(seed=5)
        for i in range(4):
            led.append({"event_id": f"e{i}"})
        return led

    def test_one_bad_signature_still_meets_quorum(self):
        led = self._ledger().tampered_copy()
        led.blocks[1]["signatures"]["validator-1"] = "00" * 64
        self.assertTrue(led.verify().valid)

    def test_two_bad_signatures_break_quorum(self):
        led = self._ledger().tampered_copy()
        for v in ("validator-1", "validator-2"):
            led.blocks[1]["signatures"][v] = "00" * 64
        self.assertFalse(led.verify().valid)

    def test_three_compromised_keys_can_forge(self):
        # Documents the stated limitation: a 3-key adversary signs arbitrary blocks.
        led = self._ledger().tampered_copy()
        from metatwin_guard.crypto import hash_obj
        body = dict(led.blocks[-1]["body"], event_id="forged")
        h = hash_obj(body)
        sigs = {f"validator-{i}": sign_hex(deterministic_private_key(f"validator-{i}", 5), bytes.fromhex(h)) for i in (1, 2, 3)}
        sigs["validator-4"] = "00" * 64
        led.blocks[-1] = {"body": body, "block_hash": h, "signatures": sigs}
        self.assertTrue(led.verify().valid)

    def test_block_deletion_detected(self):
        led = self._ledger().tampered_copy()
        del led.blocks[2]
        self.assertFalse(led.verify().valid)


class TestDetectorMath(unittest.TestCase):
    def test_isolated_binary_score_matches_paper(self):
        det = RobustDetector().fit([{f: 1.0 for f in det_features()} for _ in range(10)])
        x = {f: 1.0 for f in det_features()}
        x["power_status"] = 0.0
        r = det.evaluate(x)
        self.assertAlmostEqual(r.z["power_status"], 4.0)
        self.assertAlmostEqual(r.score, math.sqrt(16 / 7))
        self.assertFalse(r.flagged)
        self.assertEqual(r.top[0][0], "power_status")

    def test_table7_minimum_k(self):
        self.assertEqual(min_simultaneous_deviations(10.0, 3.2), 1)
        self.assertEqual(min_simultaneous_deviations(4.0, 2.5), 3)
        self.assertEqual(min_simultaneous_deviations(4.0, 3.2), 5)
        self.assertEqual(min_simultaneous_deviations(4.0, 4.0), 7)
        self.assertIsNone(min_simultaneous_deviations(2.0, 2.5))

    def test_single_feature_trigger_level(self):
        self.assertAlmostEqual(3.20 * math.sqrt(7), 8.466, places=3)

    def test_contributions_sum_to_one_and_clip(self):
        det = RobustDetector().fit([{f: float(i) for f in det_features()} for i in range(11)])
        r = det.evaluate({f: 1e9 for f in det_features()})
        self.assertTrue(all(v == 20.0 for v in r.z.values()))
        self.assertAlmostEqual(sum(r.contributions.values()), 1.0)


class TestDeterminism(unittest.TestCase):
    def test_generator_is_deterministic(self):
        a = generate_run("replay", 1)
        b = generate_run("replay", 1)
        self.assertEqual([e["signature"] for e in a.events], [e["signature"] for e in b.events])
        self.assertEqual(a.labels, b.labels)
        self.assertEqual(len(a.events), 360)
        self.assertEqual(sum(a.labels), 40)


def det_features():
    from metatwin_guard.config import FEATURES
    return FEATURES


if __name__ == "__main__":
    unittest.main()


class TestReviewRegressions(unittest.TestCase):
    """Regression tests for defects found in the v1.0.0 review."""

    def test_average_precision_handles_nan_and_none(self):
        from metatwin_guard.metrics import average_precision
        self.assertAlmostEqual(average_precision([1, 0, 1, 0], [0.9, 0.1, 0.8, 0.2]), 1.0)
        for scores in ([0.5, float("nan"), 0.9, 0.1], [float("nan"), 0.5, 0.9, 0.1], [None, 0.5, 0.9, 0.1]):
            ap = average_precision([1, 1, 0, 0], scores)
            self.assertTrue(0.0 <= ap <= 1.0, scores)

    def test_huge_integer_feature_rejected(self):
        s = make_sensor()
        guard = fitted_guard(s, 5)
        ev = make_stream(s, 1, start=50)[0]
        ev["features"]["rtt_ms"] = 10**400
        rec = guard.process(ev)
        self.assertFalse(rec["admitted"])
        self.assertEqual(rec["reasons"], ["schema:feature_rtt_ms"])

    def test_non_string_event_id_does_not_break_evidence(self):
        s = make_sensor()
        guard = fitted_guard(s, 5)
        for bad_id in (float("nan"), b"x", None, 7):
            ev = make_stream(s, 1, start=50)[0]
            ev["event_id"] = bad_id
            rec = guard.process(ev)
            self.assertFalse(rec["admitted"])
            self.assertIsNone(rec["event_id"])
        self.assertTrue(guard.ledger.verify().valid)

    def test_malformed_ledger_blocks_reported_not_raised(self):
        led = QuorumEvidenceLedger(seed=5)
        for i in range(3):
            led.append({"event_id": f"e{i}"})
        for mutate in (
            lambda b: b.pop("body"),
            lambda b: b.pop("block_hash"),
            lambda b: b.__setitem__("signatures", None),
            lambda b: b.__setitem__("body", [1, 2]),
            lambda b: b["body"].__setitem__("x", float("nan")),
        ):
            f = led.tampered_copy()
            mutate(f.blocks[1])
            rep = f.verify()
            self.assertFalse(rep.valid)
            self.assertTrue(any(e.startswith("block 1") for e in rep.errors), rep.errors)
        f = led.tampered_copy()
        f.blocks[1] = "not a block"
        self.assertFalse(f.verify().valid)

    def test_tampered_copy_is_independent(self):
        led = QuorumEvidenceLedger(seed=5)
        led.append({"event_id": "e0"})
        f = led.tampered_copy()
        f.append({"event_id": "e1"})
        self.assertEqual((len(led.blocks), len(led.append_times_ms)), (1, 1))

    def test_modification_rejected_by_hash_or_signature_only(self):
        from metatwin_guard.benchmark import execute_run
        res = execute_run("telemetry_modification", 1)
        injected = [r for r, y in zip(res.records, res.run.labels) if y]
        self.assertEqual(len(injected), 40)
        for r in injected:
            self.assertFalse(r["admitted"])
            self.assertIn(r["reasons"], (["payload_hash_mismatch"], ["signature_invalid"]))
        normal_eval = [r for r, y in zip(res.records[res.run.n_baseline:], res.run.labels[res.run.n_baseline:]) if not y]
        self.assertEqual(len(normal_eval), 200)
        self.assertTrue(all(r["admitted"] for r in normal_eval))

    def test_strict_timestamp_format(self):
        from metatwin_guard.events import parse_ts
        self.assertEqual(parse_ts("2026-08-23T00:00:01.500000Z").microsecond, 500000)
        for bad in ("2026-08-23T00:00:01Z", "2026-08-23 00:00:01.000000Z", "2026-08-23T00:00:01.000000+00:00", 5):
            with self.assertRaises(ValueError):
                parse_ts(bad)
