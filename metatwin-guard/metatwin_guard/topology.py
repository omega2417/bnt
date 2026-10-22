"""Confirmed two-site cyber-range context (evidence level A, Table 1).

Nominal provider rates are not measured throughput. Unknown items are kept as
None rather than invented. Pseudonymous sensors map onto topology nodes.
"""
from __future__ import annotations

SITES = {
    "A": {
        "boundary_router": "Keenetic Titan",
        "wan_links_mbps_nominal": [1000, 1000, 1000, 100, 100],
        "wifi_controller": "UniFi CloudKey Gen2",
        "access_points": 48,
        "aps_with_confirmed_gigabit_uplink": 12,
        "backup_power_stations": 3,  # EcoFlow; models/capacity not supplied
        "kali_workstations": 0,
        "compute_node_confirmed": False,
    },
    "B": {
        "boundary_router": "Keenetic Viva",
        "wan_links_mbps_nominal": [1000, 1000],
        "wifi_controller": "UniFi CloudKey Gen1",
        "access_points": 6,  # 100 Mbit/s wired connections
        "aps_with_confirmed_gigabit_uplink": 0,
        "backup_power_stations": 0,
        "kali_workstations": 25,
        "compute_node_confirmed": True,
    },
}
INTER_SITE_VPN = {"protocol": None, "mtu": None, "measured_throughput_mbps": None}

NOT_SUPPLIED = [
    "router firmware", "controller versions", "access-point models", "switches",
    "VLAN/ACL/IP plan", "VPN protocol and MTU", "Kali workstation hardware",
    "EcoFlow models, capacity and loads", "authorized telemetry export/API",
]

# Pseudonymous synthetic sensors -> (site, topology node)
SENSORS = {
    "sA-edge": ("A", "A/edge-router"),
    "sB-edge": ("B", "B/edge-router"),
    "s-vpn": ("A", "A-B/vpn-path"),
    "sA-wifi": ("A", "A/unifi-ck2"),
    "sB-wifi": ("B", "B/unifi-ck1"),
    "sA-power": ("A", "A/ecoflow"),
}


def summary() -> dict:
    return {
        "provider_connections": sum(len(s["wan_links_mbps_nominal"]) for s in SITES.values()),
        "access_points": sum(s["access_points"] for s in SITES.values()),
        "backup_power_stations": sum(s["backup_power_stations"] for s in SITES.values()),
        "kali_workstations": sum(s["kali_workstations"] for s in SITES.values()),
        "inter_site_vpn": True,
    }
