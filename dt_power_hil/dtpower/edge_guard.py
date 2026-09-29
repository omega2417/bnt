"""Python mirror of the ESP32 edge_guard firmware logic (firmware/esp32_edge_guard).

Implements the state machine of section 6.5 and the command contract of 6.4.
The same test vectors are used for this model and the C firmware, so the
emulated controller behaves as the firmware is specified to behave.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCHEMA = "1.0"
INIT, READY, RUNNING, DEGRADED, STOPPED = "INIT", "READY", "RUNNING", "DEGRADED", "STOPPED"
ACTIONS = ("SET_AUX_ON", "SET_AUX_OFF")


@dataclass
class EdgeGuard:
    run_id: str
    boot_id: str
    mode: str
    clock_offset_s: float           # edge UTC clock minus true time
    clock_uncertainty_s: float
    stale_s: float = 5.0
    v_local_min: float = 12.4       # local aux permission (pack voltage), independent of the twin
    t_charge_min_c: float = 0.0
    state: str = INIT
    aux_out: bool = False
    last_hb_mono: float = -1e9
    seen: dict = field(default_factory=dict)
    log: list = field(default_factory=list)
    protections_ok: bool = True
    sensors_ok: bool = True

    # ---- lifecycle ---------------------------------------------------------
    def self_test(self, ok: bool = True) -> None:
        if self.state == INIT and ok:
            self.state = READY
        self.aux_out = False

    def start(self, t: float) -> None:
        if self.state == READY:
            self.state = RUNNING
            self.last_hb_mono = t

    def stop(self, reason: str, t: float) -> None:
        self.state = STOPPED
        self._set(False, t, f"stop:{reason}")

    def _set(self, on: bool, t: float, reason: str) -> None:
        if self.aux_out != on:
            self.log.append((t, "AUX_ON" if on else "AUX_OFF", reason))
        self.aux_out = on

    # ---- periodic ----------------------------------------------------------
    def heartbeat(self, t: float, payload: dict) -> None:
        if payload.get("run_id") != self.run_id:
            return
        self.last_hb_mono = t
        if self.state == DEGRADED and payload.get("reconciled"):
            self.state = RUNNING
            self.log.append((t, "STATE", "DEGRADED->RUNNING (reconciled)"))

    def tick(self, t: float, v_batt: float, temp_c: float, bms_open: bool) -> None:
        self.protections_ok = (not bms_open) and v_batt >= self.v_local_min
        if not self.protections_ok and self.aux_out:
            self._set(False, t, "local_protection")
        if self.state == RUNNING and t - self.last_hb_mono > self.stale_s:
            self.state = DEGRADED
            self.log.append((t, "STATE", "RUNNING->DEGRADED (heartbeat stale)"))
        if self.state != RUNNING and self.aux_out:
            self._set(False, t, f"state_{self.state}")

    # ---- command contract ---------------------------------------------------
    def handle_command(self, t: float, cmd: dict) -> dict:
        now_utc = t + self.clock_offset_s
        reason = None
        if cmd.get("schema_version") != SCHEMA:
            reason = "schema"
        elif cmd.get("mode") != self.mode:
            reason = "mode_mismatch"
        elif cmd.get("source") != "ems":
            reason = "source"
        elif cmd.get("run_id") != self.run_id:
            reason = "run_id"
        elif cmd.get("boot_id_target") != self.boot_id:
            reason = "boot_id"
        elif cmd.get("action") not in ACTIONS:
            reason = "action"
        elif cmd["expires_at_utc"] - self.clock_uncertainty_s <= now_utc:
            # conservative freshness check with the synchronisation error bound
            reason = "expired"
        cid = cmd.get("command_id")
        if reason is None and cid in self.seen:
            prev = self.seen[cid]
            return {**prev, "duplicate": True, "t_ack": t}
        if reason is None and cmd["action"] == "SET_AUX_ON":
            if self.state != RUNNING:
                reason = f"state_{self.state}"
            elif not (self.protections_ok and self.sensors_ok):
                reason = "local_permission"
        accepted = reason is None
        if accepted:
            self._set(cmd["action"] == "SET_AUX_ON", t, f"cmd:{cid}")
        ack = {"command_id": cid, "accepted": accepted, "reject_reason": reason or "",
               "t_ack": t, "aux_out": self.aux_out, "state": self.state, "duplicate": False}
        if accepted:
            self.seen[cid] = ack
        self.log.append((t, "ACK" if accepted else "REJECT", f"{cid}:{reason or 'ok'}"))
        return ack
