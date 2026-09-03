"""Concrete asset inventory of the two sites, including the 25 Kali nodes.

The counts here are the documented ones (48+6 access points are owned by the
Wi-Fi federate; this module owns everything else). Roles determine both the
power group and the default power envelope.
"""

from __future__ import annotations

from typing import Any

from .asset import Asset

__all__ = ["build_fleet", "ROLE_PROFILES"]

#: role -> (power_group, idle_w, active_w, boot_s)
ROLE_PROFILES: dict[str, tuple[int, float, float, float]] = {
    "router": (1, 14.0, 26.0, 60.0),
    "switch": (1, 20.0, 45.0, 40.0),
    "vpn_gateway": (1, 10.0, 18.0, 35.0),
    "monitoring_gateway": (1, 8.0, 15.0, 30.0),
    "controller": (2, 7.0, 12.0, 90.0),
    "log_server": (2, 35.0, 90.0, 120.0),
    "edge_ai": (2, 15.0, 45.0, 90.0),
    "workstation": (3, 25.0, 85.0, 55.0),
    "kali_workstation": (3, 22.0, 78.0, 50.0),
}


def _make(asset_id: str, site_id: str, role: str) -> Asset:
    group, idle, active, boot = ROLE_PROFILES[role]
    return Asset(asset_id, site_id, role, power_group=group, idle_power_w=idle,
                 active_power_w=active, boot_time_s=boot)


def build_fleet(sites: dict[str, Any]) -> dict[str, list[Asset]]:
    """Instantiate every non-AP asset described by the inventory."""

    fleet: dict[str, list[Asset]] = {}
    for site_id, site in sites.items():
        prefix = "A" if site_id.endswith("a") else "B"
        assets = [
            _make(f"{prefix}-RTR-1", site_id, "router"),
            _make(f"{prefix}-SW-1", site_id, "switch"),
            _make(f"{prefix}-VPN-1", site_id, "vpn_gateway"),
            _make(f"{prefix}-MON-1", site_id, "monitoring_gateway"),
            _make(f"{prefix}-CK-1", site_id, "controller"),
            _make(f"{prefix}-LOG-1", site_id, "log_server"),
            _make(f"{prefix}-AI-1", site_id, "edge_ai"),
        ]
        for index in range(int(site.get("training_workstations", 0))):
            assets.append(_make(f"{prefix}-WS-{index + 1:02d}", site_id, "workstation"))
        for index in range(int(site.get("kali_workstations", 0))):
            assets.append(_make(f"{prefix}-KALI-{index + 1:02d}", site_id,
                                "kali_workstation"))
        fleet[site_id] = assets
    return fleet
