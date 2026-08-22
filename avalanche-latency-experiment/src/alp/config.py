"""Single source of truth for the experimental protocol.

Every number that the protocol fixes in advance lives here.  Analysis
code, the simulator, the tables and the tests all read these values, so
a protocol amendment is a one-file, version-controlled change.

Value classes follow section 1.1 of the protocol:

``CONFIRMED``      stated in the laboratory description;
``PROTOCOL``       chosen in advance for the reproducible campaign;
``DERIVED``        arithmetic consequence of the two above;
``MODEL``          reference-simulator parameter (not a measurement);
``DATA_REQUIRED``  can only be filled from raw logs of a real campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Global determinism
# --------------------------------------------------------------------------
#: Master seed of the campaign.  Derived seeds are produced by
#: :func:`derive_seed`, never by re-using the master seed directly.
MASTER_SEED: int = 20260822

TIMEZONE: str = "Europe/Kyiv"


def derive_seed(*parts: object, master: int = MASTER_SEED) -> int:
    """Deterministically derive a 63-bit sub-seed from ``parts``.

    Uses BLAKE2b over the master seed and the string form of the parts,
    so the same logical stream always gets the same seed regardless of
    execution order or of how many runs precede it.
    """
    import hashlib

    payload = "|".join([str(master), *(str(p) for p in parts)]).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") >> 1


# --------------------------------------------------------------------------
# Factors (protocol section 4, Table 4)
# --------------------------------------------------------------------------

#: Block-production profiles.  ``C0`` is the unchanged (stock) configuration
#: of the same platform version and is the paired baseline.
CONFIGS: List[str] = ["C0", "C1", "C2", "C3", "C4"]

#: Target ``min-delay-target`` in milliseconds per configuration.
#: ``C0`` has no protocol-imposed target; the stock effective pacing of the
#: deployed version is a DATA_REQUIRED field and, for the reference model
#: only, is represented by :data:`STOCK_BLOCK_MS`.
CONFIG_BLOCK_MS: Dict[str, Optional[int]] = {
    "C0": None,
    "C1": 1000,
    "C2": 750,
    "C3": 500,
    "C4": 250,
}

#: MODEL value: pacing assumed for the stock profile inside the reference
#: simulator.  A real campaign replaces this with the observed interval.
STOCK_BLOCK_MS: int = 2000

BASELINE_CONFIG: str = "C0"

#: Topologies (protocol Table 6).  ``T2`` is emulated with ``tc netem``
#: until a third physical or cloud site is documented.
TOPOLOGIES: List[str] = ["T0_local", "T1_vpn", "T2_three_region_emulated"]

TOPOLOGY_LABELS: Dict[str, str] = {
    "T0_local": "T0 local",
    "T1_vpn": "T1 physical VPN",
    "T2_three_region_emulated": "T2 three-region (emulated)",
}

#: Offered load in transactions per second.
LOADS_TPS: List[int] = [25, 50, 100, 200, 400]

#: Repeats per cell of the full campaign.
REPEATS: int = 10

#: Run phases in seconds (protocol equation 2).
WARMUP_S: int = 60
MEASURE_S: int = 300
DRAIN_S: int = 60

#: Number of Kali Linux load generators (CONFIRMED by the laboratory
#: description).  One EVM account per generator avoids nonce conflicts.
N_CLIENTS: int = 25

#: Client-side polling interval for receipts and confirmed reads, seconds.
#: This is the discretisation floor of ``T_visible`` (protocol 15.2).
POLL_S: float = 0.025

#: Per-transaction end-to-end timeout, seconds.
TIMEOUT_S: float = 30.0

#: Validators and independent read nodes (protocol section 2.1: a
#: reproducible placement, not a confirmed inventory).
VALIDATORS: Dict[str, str] = {"V1": "A", "V2": "A", "V3": "A", "V4": "B", "V5": "B"}
READ_NODES: Dict[str, str] = {"R1": "A", "R2": "B"}


# --------------------------------------------------------------------------
# Statistical plan (protocol section 11)
# --------------------------------------------------------------------------

QUANTILES: Tuple[float, ...] = (0.50, 0.95, 0.99)
BOOTSTRAP_REPLICATES: int = 10_000
BOOTSTRAP_SEED: int = MASTER_SEED
CI_LEVEL: float = 0.95

#: Primary endpoint of the confirmatory family.
PRIMARY_ENDPOINT: str = "p99_ms"

#: Relative half-width of the p99 CI above which extra repeats are added.
CI_HALFWIDTH_TRIGGER: float = 0.10
EXTRA_REPEAT_BLOCK: int = 5
MAX_REPEATS: int = 30

#: Practical-equivalence band used when selecting the best static profile.
EQUIVALENCE_BAND: float = 0.05


# --------------------------------------------------------------------------
# Pre-registered stability thresholds (protocol Table 13)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class StabilityThresholds:
    """Regime-classification rules, fixed before any data is inspected."""

    min_success_rate_pct: float = 99.5
    min_consistency_pct: float = 100.0
    #: A run is unstable when the 95% CI of the Theil-Sen queue slope is
    #: strictly positive (confirmed backlog accumulation).
    queue_slope_ci_must_include_zero: bool = True
    max_p99_drift_pct: float = 20.0
    #: A tail drift is counted only when it also exceeds one client polling
    #: interval.  Below that the change is not measurable: it is a single
    #: step of the 25 ms discretisation grid, not a degrading regime.
    min_p99_drift_ms: float = 25.0
    max_healthcheck_gap_s: float = 5.0
    cpu_saturation_pct: float = 95.0
    cpu_saturation_window_s: float = 30.0

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


THRESHOLDS = StabilityThresholds()


# --------------------------------------------------------------------------
# Campaign profiles
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignProfile:
    """A concrete size of the campaign.

    ``full`` is the pre-registered protocol.  ``demo`` and ``smoke`` keep
    every factor level but shorten the measurement window and the number
    of repeats so the whole pipeline fits a Google Colab session.
    """

    name: str
    configs: List[str]
    topologies: List[str]
    loads_tps: List[int]
    repeats: int
    measure_s: int
    warmup_s: int
    drain_s: int
    description: str

    @property
    def n_runs(self) -> int:
        """Equation (1): ``N_runs = N_C * N_T * N_lambda * N_r``."""
        return (
            len(self.configs) * len(self.topologies) * len(self.loads_tps) * self.repeats
        )

    @property
    def t_run_s(self) -> int:
        """Equation (2): warm-up + measurement + drain."""
        return self.warmup_s + self.measure_s + self.drain_s

    @property
    def wall_clock_s(self) -> int:
        """Equation (3): minimum machine time, restarts excluded."""
        return self.n_runs * self.t_run_s

    @property
    def n_scheduled_tx(self) -> int:
        """Equation (4): scheduled transactions inside measurement windows."""
        return (
            self.measure_s
            * sum(self.loads_tps)
            * len(self.configs)
            * len(self.topologies)
            * self.repeats
        )

    def as_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d.update(
            n_runs=self.n_runs,
            t_run_s=self.t_run_s,
            wall_clock_s=self.wall_clock_s,
            wall_clock_h=round(self.wall_clock_s / 3600.0, 2),
            n_scheduled_tx=self.n_scheduled_tx,
        )
        return d


FULL = CampaignProfile(
    name="full",
    configs=list(CONFIGS),
    topologies=list(TOPOLOGIES),
    loads_tps=list(LOADS_TPS),
    repeats=REPEATS,
    measure_s=MEASURE_S,
    warmup_s=WARMUP_S,
    drain_s=DRAIN_S,
    description="Pre-registered campaign: 750 runs, 34 875 000 scheduled TX, 87.50 h.",
)

DEMO = CampaignProfile(
    name="demo",
    configs=list(CONFIGS),
    topologies=list(TOPOLOGIES),
    loads_tps=list(LOADS_TPS),
    repeats=3,
    measure_s=20,
    warmup_s=5,
    drain_s=5,
    description="Colab-sized campaign: every factor level, shortened window.",
)

SMOKE = CampaignProfile(
    name="smoke",
    configs=list(CONFIGS),
    topologies=["T0_local", "T1_vpn"],
    loads_tps=[25, 100],
    repeats=2,
    measure_s=5,
    warmup_s=2,
    drain_s=2,
    description="Continuous-integration smoke campaign.",
)

PROFILES: Dict[str, CampaignProfile] = {p.name: p for p in (FULL, DEMO, SMOKE)}

DEFAULT_PROFILE = "demo"


def get_profile(name: str) -> CampaignProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:  # pragma: no cover - guarded by the CLI
        raise KeyError(
            f"unknown campaign profile {name!r}; choose one of {sorted(PROFILES)}"
        ) from exc


# --------------------------------------------------------------------------
# Confirmed laboratory inventory (protocol Table 3)
# --------------------------------------------------------------------------

CONFIRMED_INVENTORY: Dict[str, object] = {
    "sites": 2,
    "site_a": {
        "role": "main building",
        "edge_router": "Keenetic Titan",
        "wan_gbps": [1.0, 1.0, 1.0, 0.1, 0.1],
        "controller": "UniFi CloudKey Gen2",
        "access_points": 48,
        "access_points_gigabit_uplink": 12,
        "power_backup_nodes": 3,
    },
    "site_b": {
        "role": "branch",
        "edge_router": "Keenetic Viva",
        "wan_gbps": [1.0, 1.0],
        "controller": "UniFi CloudKey Gen1",
        "access_points": 6,
        "access_point_uplink_gbps": 0.1,
        "kali_workstations": 25,
    },
    "inter_site": "protected site-to-site VPN",
}

#: Fields that no provided source fills in.  The CLI refuses to label a
#: dataset ``MEASURED`` while any of these is empty.
DATA_REQUIRED_FIELDS: List[str] = [
    "campaign_date",
    "responsible_person",
    "avalanchego_version",
    "avalanchego_commit",
    "subnet_evm_version",
    "subnet_evm_commit",
    "network_upgrade",
    "os_distribution",
    "os_kernel",
    "chain_id",
    "subnet_id",
    "blockchain_id",
    "genesis_sha256",
    "gas_limit",
    "fee_config",
    "contract_address",
    "contract_bytecode_sha256",
    "abi_sha256",
    "solc_version",
    "validator_inventory",
    "read_node_inventory",
    "vpn_protocol",
    "vpn_mtu",
    "clock_source",
    "clock_max_offset_ms",
    "rtt_matrix_measured",
    "python_web3_version",
]
