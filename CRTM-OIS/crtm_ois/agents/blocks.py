"""Block agents B0-B8 and the control-unit agent CU.

The structural model of the manuscript (Figure 2) is realised as a team of
agents that communicate only through the bus topics of Table 3. A block fires
when all of its input buses for the same run (correlation id) have arrived and
the control unit has issued `start`. A failure code from B2 stops the chain.
"""
from __future__ import annotations

from collections import defaultdict

from ..model import Configuration
from ..system import (AssessmentError, Trace, stage0_input, stage1_form, stage2_verify,
                      stage3_normalize, stage4_aggregate, stage5_rollup, stage6_integral,
                      stage7_robust)
from .bus import Agent, Message, MessageBus


class BlockAgent(Agent):
    inputs: tuple[str, ...] = ()
    output: str = ""

    def __init__(self, bus: MessageBus, cfg_ref: "ConfigRef", name: str):
        super().__init__(bus, name)
        self.cfg_ref = cfg_ref
        self._pending: dict[int, dict] = defaultdict(dict)
        for t in self.inputs:
            self.on(t, self._receive)
        self.on("C", self._control)

    @property
    def cfg(self) -> Configuration:
        return self.cfg_ref.cfg

    def _control(self, msg: Message) -> None:
        if msg.payload.get("command") == "stop":
            self._pending.pop(msg.corr, None)

    def _receive(self, msg: Message) -> None:
        box = self._pending[msg.corr]
        box[msg.topic] = msg.payload
        if all(t in box for t in self.inputs):
            payload = self._pending.pop(msg.corr)
            try:
                out = self.compute(payload, msg.corr)
            except AssessmentError as e:
                self.send("C", {"status": e.code, "block": self.name, "detail": e.detail}, msg.corr)
                return
            if out is not None:
                self.send(self.output, out, msg.corr)
                self.send("C", {"status": "OK", "block": self.name}, msg.corr)

    def compute(self, inp: dict, corr: int):  # pragma: no cover - abstract
        raise NotImplementedError


class ConfigRef:
    """Shared, versioned reference to the configuration (owned by B1)."""

    def __init__(self, cfg: Configuration):
        self.cfg = cfg


class B0Input(BlockAgent):
    role = "Input interface"
    inputs = ("sheet",)
    output = "X"

    def compute(self, inp, corr):
        return stage0_input(inp["sheet"])


class B1Config(BlockAgent):
    role = "Scenario and configuration"
    inputs = ("X",)
    output = "XiWK"

    def compute(self, inp, corr):
        conf = stage1_form(self.cfg, inp["X"])
        return conf


class B2Verify(BlockAgent):
    role = "Verification and completeness"
    inputs = ("XiWK",)
    output = "O"

    def compute(self, inp, corr):
        obs = stage2_verify(self.cfg, inp["XiWK"])
        return {"obs": obs, "conf": inp["XiWK"]}


class B3Normalize(BlockAgent):
    role = "Normalizer"
    inputs = ("O",)
    output = "M"

    def compute(self, inp, corr):
        o = inp["O"]
        return {"norm": stage3_normalize(self.cfg, o["conf"], o["obs"]), "obs": o["obs"]}


class B4Aggregate(BlockAgent):
    role = "Action aggregator"
    inputs = ("M",)
    output = "A"

    def compute(self, inp, corr):
        m = inp["M"]
        return stage4_aggregate(self.cfg, m["obs"], m["norm"])


class B5Rollup(BlockAgent):
    role = "Goal roll-up"
    inputs = ("A",)
    output = "G"

    def compute(self, inp, corr):
        return {"G": stage5_rollup(self.cfg, inp["A"]), "A": inp["A"]}


class B6Integral(BlockAgent):
    role = "Integral index and classifier"
    inputs = ("G",)
    output = "R"

    def compute(self, inp, corr):
        g = inp["G"]
        R = stage6_integral(self.cfg, g["A"], g["G"])
        return {"R": R, "G": g["G"], "A": g["A"]}


class B7Robust(BlockAgent):
    role = "Robustness analyzer"
    inputs = ("M",)
    output = "P"

    def __init__(self, *a, n: int = 20_000, **kw):
        super().__init__(*a, **kw)
        self.n = n
        self.enabled = True

    def compute(self, inp, corr):
        if not self.enabled or self.n <= 0:
            return {"skipped": True}
        m = inp["M"]
        P = stage7_robust(self.cfg, m["obs"], m["norm"], n=self.n)
        P.pop("samples", None)
        return P


class B8Report(BlockAgent):
    role = "Report and trace register"
    inputs = ("R", "P")
    output = "report"

    def compute(self, inp, corr):
        rep = dict(inp["R"]["R"])
        rep["goals"] = [inp["R"]["G"][g]["mean"] for g in self.cfg.goals]
        rep["actions"] = {c: a["mu"] for c, a in inp["R"]["A"].items()}
        rep["P"] = inp["P"]
        rep["config_version"] = self.cfg.version
        rep["corr"] = corr
        rep["tick"] = self.bus.tick
        trace = Trace(self.cfg.version, self.cfg.seed)
        for m in self.bus.messages(corr=corr):
            if m.topic in ("X", "XiWK", "O", "M", "A", "G", "R", "P", "C"):
                trace.write(m.topic, m.sender, m.payload)
        rep["trace_len"] = len(trace.records)
        return rep


class ControlUnit(Agent):
    """CU: sequences the blocks through the control bus C and records statuses."""
    name = "CU"
    role = "Control unit"

    def __init__(self, bus: MessageBus, cfg_ref: ConfigRef):
        super().__init__(bus)
        self.cfg_ref = cfg_ref
        self._corr = 0
        self.status: dict[int, list] = defaultdict(list)
        self.failures: dict[int, dict] = {}
        self.on("C", self._status)

    def start(self, sheet: dict) -> int:
        self._corr += 1
        c = self._corr
        self.send("C", {"command": "start", "version": self.cfg_ref.cfg.version}, c)
        self.send("sheet", sheet, c)
        return c

    def _status(self, msg: Message) -> None:
        st = msg.payload.get("status")
        if st is None:
            return
        self.status[msg.corr].append((msg.payload.get("block"), st))
        if st != "OK" and msg.corr not in self.failures:
            self.failures[msg.corr] = msg.payload
            self.send("C", {"command": "stop", "status": st}, msg.corr)


def build_block_team(bus: MessageBus, cfg: Configuration, mc_samples: int = 20_000):
    ref = ConfigRef(cfg)
    cu = ControlUnit(bus, ref)
    blocks = [B0Input(bus, ref, "B0"), B1Config(bus, ref, "B1"), B2Verify(bus, ref, "B2"),
              B3Normalize(bus, ref, "B3"), B4Aggregate(bus, ref, "B4"), B5Rollup(bus, ref, "B5"),
              B6Integral(bus, ref, "B6"), B7Robust(bus, ref, "B7", n=mc_samples), B8Report(bus, ref, "B8")]
    return ref, cu, blocks
