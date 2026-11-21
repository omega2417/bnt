"""Fast regression tests: python -m pytest tests  (or python tests/test_meshrtc.py)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from meshrtc import protocol as pr
from meshrtc.world import World
from meshrtc.sim import Config, Sim, run_paired
from meshrtc.scenarios import SCENARIOS, run_scenario
from meshrtc.fleet import FleetLogic

W = World()


def test_roundtrip_all_commands():
    cmds = [pr.TSK(17, 3, 5, 860), pr.RS(3, 217, 0.41, 182, 2), pr.DEC(3, "RET", "P1", 0.27), pr.DEC(2, "RTG", "R7", 0.5),
            pr.BLK(3, 447), pr.RCP(17, 3, 822, 3), pr.CLS(3, 5), pr.REQ(4, 1, 2, 1, 21), pr.BID(21, 2, 845),
            pr.LSE(21, 2), pr.RTB(3, 1), pr.RLY(9, 133), pr.ZSET(2.33), pr.RPT(0), pr.ACK(77), pr.HLD(3, 30)]
    for c in cmds:
        assert pr.decode_text(c.text()).f == c.f
        assert pr.decode_binary(c.binary()).f == pr.decode_text(c.text()).f
        assert len(c.binary()) < len(c.text())
        assert pr.validate(c) == []


def test_crc_rejects_corruption():
    b = bytearray(pr.TSK(1, 2, 3, 600).binary())
    b[2] ^= 1
    try:
        pr.decode_binary(bytes(b))
        assert False
    except ValueError:
        pass


def test_airtime_matches_article():
    # routing ACK: 37.5 / 130 / 477 ms (SHORT_FAST / MEDIUM_FAST / LONG_FAST)
    for p, ms in (("SHORT_FAST", 37.5), ("MEDIUM_FAST", 130), ("LONG_FAST", 477)):
        assert abs(pr.lora_airtime(pr.ACK_FRAME_B, p) * 1000 - ms) < 1.0


def test_validator_catches_bad_command():
    assert pr.validate(pr.TSK(1, 3, 3, 600))          # fallback == recipient
    assert pr.validate(pr.Command("TSK", dict(task=1, site=12, alt=1, deadline=1, z=1, oneway=0)))


def test_sfc_never_strands_in_small_batch():
    for seed in range(12):
        out = run_paired(W, Config(soc0=0.5, H=24, k=2, b=0.1), ("S3",), seed=seed)
        m = out["S3"].mission_metrics()[0]
        assert not m["stranded"], m


def test_all_scenarios_run():
    for sid in SCENARIOS:
        sim = run_scenario(W, sid)
        assert len(sim.packets) > 0
        if sim.cfg.fleet:
            assert FleetLogic.metrics(sim)["n"] > 0


def test_closure_triggers_retarget():
    sim = run_scenario(W, "S02")
    codes = [d[2] for d in sim.robots[0].decisions]
    assert "RTG" in codes
    assert any(p.cmd.op == "CLS" for p in sim.packets)


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)


def test_shield_blocks_faulty_policy():
    class Faulty:
        def act(self, f):
            return "CONTINUE"
    lost = {True: 0, False: 0}
    for shield in (True, False):
        for r in range(10):
            cfg = Config(soc0=0.35, H=24, k=2, b=0.1, policy_model=Faulty(), shield=shield)
            m = Sim(W, cfg, seed=90_000 + r, strategy="NNP").run().mission_metrics()[0]
            lost[shield] += m["terminal"] in ("depleted", "stopped", "stuck")
    assert lost[True] == 0 and lost[False] > 0
