"""Scenario matrix E01–E11 (protocol section 12), frozen before the campaign."""
from __future__ import annotations

import numpy as np

from .bench import Scenario
from .profiles import step_profile

MIN = 60


def e01():
    n = 60 * MIN
    gen = step_profile([(15 * MIN, 25.0), (22.5 * MIN, 10.0), (22.5 * MIN, 60.0)])
    return Scenario("E01", n, gen, np.full(n, 18.0), np.zeros(n, bool), 0.60, stop_soc_ref=None,
                    note="15 min stabilisation; gen<demand segment; gen>demand segment; aux off")


def e02():
    n = 60 * MIN
    aux = step_profile([(15 * MIN, 0), (15 * MIN, 1), (15 * MIN, 0), (15 * MIN, 1)]).astype(bool)
    return Scenario("E02", n, np.full(n, 25.0), np.full(n, 18.0), aux, 0.60, stop_soc_ref=None,
                    note="18 W base; +30 W aux at 15 min, off at 30, on at 45")


def e03():
    n = 120 * MIN
    gen = step_profile([(30 * MIN, 60.0), (60 * MIN, 10.0), (30 * MIN, 60.0)])
    return Scenario("E03", n, gen, np.full(n, 18.0), np.ones(n, bool), 0.50,
                    note="60 W 30 min / 10 W 60 min / 60 W 30 min on the bus; aux scheduled")


def e04():
    n = 90 * MIN
    gen = step_profile([(15 * MIN, 55.0), (60 * MIN, 0.0), (15 * MIN, 55.0)])
    return Scenario("E04", n, gen, np.full(n, 18.0), np.zeros(n, bool), 0.60,
                    note="main source 55 W lost for 60 min; battery-only operation; aux off")


def e05():
    n = 360 * MIN
    gen = step_profile([(90 * MIN, 40.0), (180 * MIN, 5.0), (90 * MIN, 60.0)])
    return Scenario("E05", n, gen, np.full(n, 18.0), np.ones(n, bool), 0.45,
                    note="deficit: 40 W 1.5 h / 5 W 3 h / 60 W 1.5 h; 18 W critical + 30 W scheduled aux; stop at SOC_ref 0.20")


def e06():
    n = 30 * MIN
    return Scenario("E06", n, np.full(n, 30.0), np.full(n, 18.0), np.ones(n, bool), 0.60,
                    blackouts=[(600, 630, "up"), (900, 930, "both")], stale_command_test_at=1200.0,
                    note="uplink telemetry stop 30 s at 600 s; bidirectional stop 30 s at 900 s; stale/wrong-run command at 1200 s")


def e07(i_work: float = 2.6):
    n = 30 * MIN
    faults = [(180, 360, "offset", 0.10 * i_work * 1.5), (540, 720, "stuck", None), (900, 960, "missing", "p_gen_bus_w"),
              (1140, 1200, "impossible", 99.0), (1380, 1560, "sign", None)]
    return Scenario("E07", n, np.full(n, 10.0), np.full(n, 18.0), np.ones(n, bool), 0.60, sensor_faults=faults,
                    note="faults injected into the twin's copy only; REF and protection see true signals")


def e08():
    n = 60 * MIN
    gen = step_profile([(20 * MIN, 0.0), (40 * MIN, 120.0)])
    return Scenario("E08", n, gen, np.full(n, 18.0), np.ones(n, bool), 0.33, stop_soc_ref=0.20,
                    note="deficit 20 min then generation restored to 120 W; hysteresis check")


ALL = {"E01": e01, "E02": e02, "E03": e03, "E04": e04, "E05": e05, "E06": e06, "E07": e07, "E08": e08}
