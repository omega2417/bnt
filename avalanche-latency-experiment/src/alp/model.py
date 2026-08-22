"""Parameters of the reference network/execution model.

These values are MODEL parameters.  They are *not* measurements of the
cyber range and must never be reported as such.  They exist so that the
whole analysis pipeline — traces, run execution, metric derivation,
statistics, stability rules, tables and figures — can be executed and
audited end to end before the real campaign produces raw logs.

When real logs arrive, nothing in this file is used: :mod:`alp.analyze`
consumes the JSONL records regardless of who produced them.

Every parameter below is stated with its justification and with the
DATA_REQUIRED field that replaces it after a real campaign.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict

from .config import STOCK_BLOCK_MS


@dataclass(frozen=True)
class TopologyModel:
    """One-way delays and stability of a network topology, milliseconds."""

    #: Client (Kali workstation) to the write RPC endpoint, one way.
    d_client_write_ms: float
    #: Client to an independent read node, one way.
    d_client_read_ms: float
    #: Transaction gossip from the ingress node to the block proposer.
    d_gossip_ms: float
    #: Consensus acceptance after a block is proposed: the Snowman* poll
    #: rounds across the validator set.  Dominated by inter-validator RTT.
    d_accept_ms: float
    #: Time for an accepted block to be applied at a read node.
    d_apply_ms: float
    #: Lognormal sigma of the per-block network jitter.
    jitter_sigma: float
    #: Probability that a consensus round needs an extra poll (slow round).
    p_slow_round: float
    #: Mean of the exponential penalty of a slow round.
    slow_round_ms: float
    #: Packet loss, fraction.  Drives retransmission-shaped tail delay.
    loss_frac: float
    #: Delay multiplier of the second (remote) read node relative to the
    #: first.  Independent read nodes sit on different sites, so state
    #: convergence between them is not instantaneous (equation 7).
    read_asymmetry: float
    #: netem target used to realise the topology (documentation only).
    netem_note: str


#: Protocol Table 6.  T0/T1 reflect the two confirmed physical sites and
#: their VPN; T2 realises the abstract three-region case with ``tc netem``
#: targets of 20/50/80 ms one-way delay, 2 ms jitter, 0.1 % loss.
TOPOLOGY_MODELS: Dict[str, TopologyModel] = {
    "T0_local": TopologyModel(
        d_client_write_ms=0.35,
        d_client_read_ms=0.35,
        d_gossip_ms=0.40,
        d_accept_ms=18.0,
        d_apply_ms=3.0,
        jitter_sigma=0.22,
        p_slow_round=0.004,
        slow_round_ms=35.0,
        loss_frac=0.0,
        read_asymmetry=1.15,
        netem_note="no netem; isolated LAN",
    ),
    "T1_vpn": TopologyModel(
        d_client_write_ms=1.2,
        d_client_read_ms=1.2,
        d_gossip_ms=4.5,
        d_accept_ms=42.0,
        d_apply_ms=9.0,
        jitter_sigma=0.34,
        p_slow_round=0.012,
        slow_round_ms=70.0,
        loss_frac=0.0005,
        read_asymmetry=1.9,
        netem_note="no netem; real site-to-site VPN path",
    ),
    "T2_three_region_emulated": TopologyModel(
        d_client_write_ms=2.0,
        d_client_read_ms=12.0,
        d_gossip_ms=22.0,
        d_accept_ms=118.0,
        d_apply_ms=34.0,
        jitter_sigma=0.42,
        p_slow_round=0.030,
        slow_round_ms=130.0,
        loss_frac=0.001,
        read_asymmetry=2.4,
        netem_note="netem delay 20/50/80 ms, jitter 2 ms, loss 0.1 %",
    ),
}


@dataclass(frozen=True)
class ExecutionModel:
    """Block production, execution and storage parameters of Subnet-EVM."""

    #: Gas limit per block. DATA_REQUIRED: genesis ``gasLimit``.
    gas_limit: int = 15_000_000
    #: Gas of one VisibilityProbe.write call: two SSTORE plus one event.
    gas_per_tx: int = 46_000
    #: Wall-clock cost of executing one probe transaction, ms.
    t_exec_ms: float = 0.55
    #: Fixed per-block cost independent of the transaction count:
    #: proposal, verification, header work, commit bookkeeping.
    t_block_fixed_ms: float = 24.0
    #: State-commit latency at the median, ms (NVMe class).
    t_commit_ms: float = 2.2
    #: Lognormal sigma of the storage-commit latency.
    commit_sigma: float = 0.55
    #: Utilisation at which storage latency starts to inflate.
    commit_knee: float = 0.65
    #: Baseline CPU of an idle validator, per cent.
    cpu_idle_pct: float = 6.0
    #: CPU cost of one block opportunity, in CPU-milliseconds: proposal,
    #: signature verification and the consensus polls of the validator set.
    #: This is the term that makes short block pacing expensive even at
    #: low offered load, which is the mechanism behind RQ2.
    cpu_ms_per_block: float = 180.0
    #: CPU cost of one executed transaction, in CPU-milliseconds.
    cpu_ms_per_tx: float = 3.2
    #: Cores dedicated to the node process.
    cpu_cores: int = 4
    #: Utilisation above which consensus rounds start to degrade, and the
    #: exponent and gain of that degradation.
    pressure_knee: float = 0.45
    pressure_gain: float = 9.0
    pressure_exponent: float = 1.5
    #: Resident memory floor and per-queued-transaction growth, MiB.
    mem_base_mib: float = 1850.0
    mem_per_queued_mib: float = 0.0009

    @property
    def gas_capacity_per_block(self) -> int:
        """Gas-limited number of probe transactions a block can hold."""
        return int(self.gas_limit // self.gas_per_tx)


EXECUTION = ExecutionModel()


def block_target_ms(config: str, stock_ms: int = STOCK_BLOCK_MS) -> float:
    """Target block interval of a configuration, in milliseconds.

    ``C0`` is the unchanged configuration: the protocol does not set its
    pacing, so the model uses :data:`alp.config.STOCK_BLOCK_MS`.  A real
    campaign replaces this with the observed interval of the deployed
    version (DATA_REQUIRED: ``observed_block_interval_stock``).
    """
    from .config import CONFIG_BLOCK_MS

    target = CONFIG_BLOCK_MS.get(config)
    return float(stock_ms if target is None else target)


def cpu_pressure(blocks_per_s: float, tx_per_s: float, exe: ExecutionModel = None) -> float:
    """Fraction of the node's CPU budget consumed at a given operating point.

    ``pressure = (a * blocks/s + b * tx/s) / (1000 * cores)`` where ``a``
    and ``b`` are the per-block and per-transaction CPU costs.  The block
    term does not vanish at low load: halving the block interval doubles
    the consensus work regardless of how many transactions arrive.
    """
    exe = exe or EXECUTION
    cpu_ms_per_s = exe.cpu_ms_per_block * blocks_per_s + exe.cpu_ms_per_tx * tx_per_s
    return cpu_ms_per_s / (1000.0 * exe.cpu_cores)


def slow_round_scale(pressure: float, exe: ExecutionModel = None) -> float:
    """Multiplier applied to the slow-round probability under CPU pressure.

    Encodes hypothesis H2: the benefit of shorter pacing is non-linear,
    because the same shortening that removes block-wait latency also
    raises the rate of degraded consensus rounds, which land in the tail.
    """
    exe = exe or EXECUTION
    excess = max(0.0, pressure - exe.pressure_knee)
    return 1.0 + exe.pressure_gain * excess**exe.pressure_exponent


def model_manifest() -> Dict[str, object]:
    """Serialisable description of the model, embedded in every passport."""
    return {
        "execution": asdict(EXECUTION),
        "gas_capacity_per_block": EXECUTION.gas_capacity_per_block,
        "stock_block_ms": STOCK_BLOCK_MS,
        "topologies": {k: asdict(v) for k, v in TOPOLOGY_MODELS.items()},
        "disclaimer": (
            "MODEL parameters of the reference simulator. Not measurements "
            "of the cyber range. Replace with campaign telemetry before "
            "reporting any value as a result."
        ),
    }
