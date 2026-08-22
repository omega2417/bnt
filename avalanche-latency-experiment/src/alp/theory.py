"""Closed-form pre-experiment calculations (protocol section 8).

These are model results under stated assumptions, not measurements.  The
protocol forbids copying them into the Results tables, so every function
here returns frames tagged ``value_class = "THEORY"`` and the table
writer prints that tag.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import pandas as pd

from .config import LOADS_TPS, MEASURE_S, QUANTILES

BLOCK_PROFILES_MS: Sequence[int] = (1000, 750, 500, 250)


def nominal_block_rate(block_ms: float) -> float:
    """Equation (15): ``f_B = 1000 / B_ms`` in blocks per second.

    This is the nominal block-opportunity rate only.  It is not TPS and it
    does not guarantee the observed interval.
    """
    if block_ms <= 0:
        raise ValueError("block interval must be positive")
    return 1000.0 / block_ms


def block_opportunities(block_ms: float, window_s: float = MEASURE_S) -> float:
    """Number of block opportunities inside a measurement window."""
    return nominal_block_rate(block_ms) * window_s


def table_nominal_rate(
    profiles: Iterable[int] = BLOCK_PROFILES_MS, window_s: float = MEASURE_S
) -> pd.DataFrame:
    """Protocol Table 9."""
    profiles = list(profiles)
    reference = nominal_block_rate(max(profiles))
    rows = [
        {
            "B_ms": b,
            "f_B_blocks_per_s": nominal_block_rate(b),
            f"blocks_per_{int(window_s)}s": block_opportunities(b, window_s),
            "relative_to_slowest": nominal_block_rate(b) / reference,
            "value_class": "THEORY",
        }
        for b in profiles
    ]
    return pd.DataFrame(rows)


def block_wait_quantile(block_ms: float, p: float) -> float:
    """Quantile of the nearest-block wait under ``W_block ~ U(0, B)``.

    Section 8.2: with an arrival phase uniform over the block cycle,
    ``Q_p(W_block) = p * B``.  This is the structural lower component of
    the latency only; propagation, acceptance, execution, commit and read
    are added separately.
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must lie in [0, 1]")
    return p * block_ms


def block_wait_mean(block_ms: float) -> float:
    """``E[W_block] = B / 2`` under the uniform-phase assumption."""
    return block_ms / 2.0


def table_block_wait(
    profiles: Iterable[int] = BLOCK_PROFILES_MS, quantiles: Sequence[float] = QUANTILES
) -> pd.DataFrame:
    """Protocol Table 10."""
    rows = []
    for b in profiles:
        row = {"B_ms": b, "E_W_ms": block_wait_mean(b)}
        for p in quantiles:
            row[f"p{int(round(p * 100))}_ms"] = block_wait_quantile(b, p)
        row["value_class"] = "THEORY"
        rows.append(row)
    return pd.DataFrame(rows)


def tx_per_block_required(load_tps: float, block_ms: float) -> float:
    """Equation (16): ``n = lambda * B_ms / 1000``.

    Mean number of transactions a block must accept so that no backlog
    accumulates at offered load ``lambda``.  It is an arithmetic mean
    requirement, not the gas-limited capacity of Subnet-EVM.
    """
    return load_tps * block_ms / 1000.0


def table_tx_per_block(
    loads: Iterable[int] = LOADS_TPS, profiles: Iterable[int] = BLOCK_PROFILES_MS
) -> pd.DataFrame:
    """Protocol Table 11."""
    profiles = list(profiles)
    rows = []
    for lam in loads:
        row = {"load_tps": lam}
        for b in profiles:
            row[f"B_{b}ms"] = tx_per_block_required(lam, b)
        row["value_class"] = "THEORY"
        rows.append(row)
    return pd.DataFrame(rows)


def campaign_arithmetic(profile) -> pd.DataFrame:
    """Equations (1)-(4) for a campaign profile, as an auditable table."""
    p = profile
    rows = [
        {
            "quantity": "N_runs",
            "formula": "N_C * N_T * N_lambda * N_r",
            "expansion": f"{len(p.configs)} * {len(p.topologies)} * "
            f"{len(p.loads_tps)} * {p.repeats}",
            "value": p.n_runs,
            "unit": "runs",
            "equation": 1,
        },
        {
            "quantity": "t_run",
            "formula": "warmup + measure + drain",
            "expansion": f"{p.warmup_s} + {p.measure_s} + {p.drain_s}",
            "value": p.t_run_s,
            "unit": "s",
            "equation": 2,
        },
        {
            "quantity": "T_wall,min",
            "formula": "N_runs * t_run",
            "expansion": f"{p.n_runs} * {p.t_run_s}",
            "value": p.wall_clock_s,
            "unit": "s",
            "equation": 3,
        },
        {
            "quantity": "T_wall,min",
            "formula": "N_runs * t_run / 3600",
            "expansion": f"{p.wall_clock_s} / 3600",
            "value": round(p.wall_clock_s / 3600.0, 2),
            "unit": "h",
            "equation": 3,
        },
        {
            "quantity": "N_TX",
            "formula": "measure_s * sum(lambda) * N_C * N_T * N_r",
            "expansion": f"{p.measure_s} * {sum(p.loads_tps)} * {len(p.configs)} * "
            f"{len(p.topologies)} * {p.repeats}",
            "value": p.n_scheduled_tx,
            "unit": "tx",
            "equation": 4,
        },
    ]
    df = pd.DataFrame(rows)
    df["value_class"] = "DERIVED"
    return df


def table_tx_per_run(
    loads: Iterable[int] = LOADS_TPS,
    window_s: int = MEASURE_S,
    repeats: int = 10,
    n_clients: int = 25,
) -> pd.DataFrame:
    """Protocol Table 5: transactions per run and per repeat block."""
    rows = []
    for lam in loads:
        rows.append(
            {
                "load_tps": lam,
                "per_client_tps": lam / n_clients,
                f"tx_per_{window_s}s": lam * window_s,
                f"tx_per_{repeats}_repeats": lam * window_s * repeats,
                "value_class": "DERIVED",
            }
        )
    return pd.DataFrame(rows)
