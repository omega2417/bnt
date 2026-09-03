"""Inter-site VPN surrogate (section 9.3).

Until the tunnel is inventoried this is a configurable surrogate, not a
vendor-exact implementation: protocol, MTU and measured baseline stay
``UNINVENTORIED`` and every derived record is flagged ``ASSUMED_PARAMETER``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

__all__ = ["VpnTunnel", "VpnState"]


class VpnState:
    UP = "UP"
    DEGRADED = "DEGRADED"
    REKEYING = "REKEYING"
    DOWN = "DOWN"
    RECONNECTING = "RECONNECTING"


@dataclass
class VpnTunnel:
    tunnel_id: str = "A-B"
    base_overhead_ms: float = 4.0
    mtu: Any = "UNINVENTORIED"
    protocol: Any = "UNINVENTORIED"
    rekey_period_s: int = 3600
    rekey_duration_s: int = 2
    reconnect_s: int = 6
    state: str = VpnState.UP
    latency_add_ms: float = 0.0
    loss_add_pct: float = 0.0
    down_until_s: float = -1.0
    rekey_until_s: float = -1.0
    reconnects: int = 0
    rekeys: int = 0
    buffered_records: int = 0

    def apply_scenario(self, *, latency_add_ms: float = 0.0, loss_add_pct: float = 0.0,
                       force_down: bool = False, rekey: bool = False, t_s: float = 0.0) -> None:
        self.latency_add_ms = max(0.0, latency_add_ms)
        self.loss_add_pct = max(0.0, loss_add_pct)
        if force_down and self.state != VpnState.DOWN:
            self.state = VpnState.DOWN
            self.down_until_s = t_s + self.reconnect_s
        if rekey and self.state == VpnState.UP:
            self.state = VpnState.REKEYING
            self.rekey_until_s = t_s + self.rekey_duration_s
            self.rekeys += 1

    def step(self, t_s: float, rng: random.Random, underlay_up: bool) -> dict[str, Any]:
        if not underlay_up:
            if self.state != VpnState.DOWN:
                self.state = VpnState.DOWN
                self.down_until_s = t_s + self.reconnect_s
        elif self.state == VpnState.DOWN and t_s >= self.down_until_s:
            self.state = VpnState.RECONNECTING
            self.reconnects += 1
        elif self.state == VpnState.RECONNECTING:
            self.state = VpnState.UP
        elif self.state == VpnState.REKEYING and t_s >= self.rekey_until_s:
            self.state = VpnState.UP
        elif self.state == VpnState.UP and self.rekey_period_s > 0 \
                and int(t_s) % self.rekey_period_s == 0 and t_s > 0:
            self.state = VpnState.REKEYING
            self.rekey_until_s = t_s + self.rekey_duration_s
            self.rekeys += 1
        elif self.state == VpnState.UP and (self.latency_add_ms > 0 or self.loss_add_pct > 0):
            self.state = VpnState.DEGRADED
        elif self.state == VpnState.DEGRADED and self.latency_add_ms == 0 \
                and self.loss_add_pct == 0:
            self.state = VpnState.UP

        carrying = self.state in (VpnState.UP, VpnState.DEGRADED)
        if carrying:
            delivered = self.buffered_records
            self.buffered_records = 0
        else:
            delivered = 0
            self.buffered_records = min(100_000, self.buffered_records + 1)

        overhead = self.base_overhead_ms + self.latency_add_ms
        if self.state == VpnState.REKEYING:
            overhead += 15.0 + abs(rng.gauss(0.0, 3.0))
        return {
            "vpn_state": self.state,
            "vpn_latency_ms": 0.0 if not carrying else overhead,
            "vpn_loss_pct": 100.0 if not carrying else self.loss_add_pct,
            "vpn_carrying": carrying,
            "vpn_reconnects": self.reconnects,
            "vpn_rekeys": self.rekeys,
            "vpn_buffered_records": self.buffered_records,
            "vpn_burst_delivered": delivered,
            "mtu_status": "UNINVENTORIED" if self.mtu == "UNINVENTORIED" else "CONFIGURED",
        }

    def reset(self) -> None:
        self.state = VpnState.UP
        self.latency_add_ms = self.loss_add_pct = 0.0
        self.reconnects = self.rekeys = self.buffered_records = 0
