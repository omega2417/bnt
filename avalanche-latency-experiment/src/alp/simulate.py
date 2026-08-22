"""Reference simulator of one run of the field experiment.

The simulator is a discrete-event model of the measured path defined in
protocol section 6:

    submit -> RPC ingress -> gossip -> block inclusion -> consensus
    acceptance -> execution -> state commit -> first confirmed read

It exists for one reason: to exercise the *whole* pipeline — traces,
per-transaction records, metric derivation, the statistical plan, the
stability rules, the tables and the figures — before the cyber-range
campaign produces raw logs, and to let a reviewer re-run every step.

Everything it writes carries ``provenance = "SIMULATED"``.  The analysis
code treats simulated and measured records identically, and every table
and figure prints the provenance of the dataset it was built from.

Model summary
-------------
* Blocks are produced on a fixed cadence ``B`` (the ``min-delay-target``
  of the profile).  A block admits ``min(backlog, gas_limit/gas_per_tx)``
  transactions; when the previous block's execution cost exceeds ``B``,
  the next proposal slips, so the observed interval inflates under load.
* Consensus acceptance is a per-block delay: a lognormal-jittered base
  plus a Bernoulli "slow round" penalty.  Because the penalty is drawn per
  block, latency is correlated inside a block, exactly as on a real chain
  — which is why the statistical plan treats the *run*, not the
  transaction, as the inferential unit.
* Read nodes apply the accepted block after an independent per-node
  delay, and the client discovers the new state on a 25 ms polling grid,
  reproducing the discretisation error discussed in protocol 15.2.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import PROVENANCE_SIMULATED, __version__
from .config import (
    CampaignProfile,
    POLL_S,
    READ_NODES,
    TIMEOUT_S,
    derive_seed,
    get_profile,
)
from .model import (
    EXECUTION,
    TOPOLOGY_MODELS,
    block_target_ms,
    cpu_pressure,
    model_manifest,
    slow_round_scale,
)
from .traces import TraceSpec, build_trace, trace_sha256

#: Offset applied to every client monotonic clock so that the emitted
#: ``t_*_ns`` values look like ``time.perf_counter_ns()`` output rather
#: than starting at zero.  Deterministic, per run.
_CLOCK_BASE_NS = 1_000_000_000_000


@dataclass
class RunSpec:
    """Identity and factor levels of one run."""

    run_id: str
    config: str
    topology: str
    load_tps: int
    repeat: int
    trace_id: str
    measure_s: int
    warmup_s: int
    drain_s: int

    def key(self) -> str:
        return f"{self.run_id}|{self.config}|{self.topology}|{self.load_tps}|{self.repeat}"


def _lognormal_factor(rng: np.random.Generator, sigma: float, size) -> np.ndarray:
    """Multiplicative jitter with unit mean and the given lognormal sigma."""
    if sigma <= 0:
        return np.ones(size)
    return rng.lognormal(mean=-0.5 * sigma**2, sigma=sigma, size=size)


def _simulate_blocks(
    t_ready_ms: np.ndarray,
    block_ms: float,
    horizon_ms: float,
    rng: np.random.Generator,
    topo,
    exe=EXECUTION,
    slow_scale: float = 1.0,
):
    """Assign transactions to blocks and time every block stage.

    Returns arrays indexed by transaction (block index, -1 if never
    included) and per-block arrays of proposal/accept/commit times.
    """
    n_tx = t_ready_ms.size
    capacity = exe.gas_capacity_per_block

    order = np.argsort(t_ready_ms, kind="stable")
    ready_sorted = t_ready_ms[order]

    block_of_sorted = np.full(n_tx, -1, dtype=np.int64)
    proposal_ms: List[float] = []
    count: List[int] = []

    ptr = 0
    t_prop = 0.0
    prev_service = 0.0
    # Blocks keep being produced while the horizon has not elapsed or while
    # a backlog remains (the drain phase).
    while t_prop <= horizon_ms or ptr < n_tx:
        hi = int(np.searchsorted(ready_sorted, t_prop, side="right"))
        take = min(hi - ptr, capacity)
        if take > 0:
            block_of_sorted[ptr : ptr + take] = len(proposal_ms)
            ptr += take
        proposal_ms.append(t_prop)
        count.append(take)

        service = exe.t_block_fixed_ms + take * exe.t_exec_ms
        step = max(block_ms, prev_service)
        prev_service = service
        t_prop += step
        # Safety valve: never spin forever on a pathological configuration.
        if len(proposal_ms) > 4_000_000:  # pragma: no cover
            break

    proposal = np.asarray(proposal_ms, dtype=np.float64)
    n_in_block = np.asarray(count, dtype=np.int64)
    n_blocks = proposal.size

    # Per-block consensus acceptance: jittered base plus slow-round penalty.
    accept_delay = topo.d_accept_ms * _lognormal_factor(rng, topo.jitter_sigma, n_blocks)
    slow = rng.random(n_blocks) < min(topo.p_slow_round * slow_scale, 0.5)
    accept_delay += slow * rng.exponential(topo.slow_round_ms, n_blocks)
    if topo.loss_frac > 0:
        # A lost consensus message costs one extra poll round trip.
        lost = rng.random(n_blocks) < topo.loss_frac * 4
        accept_delay += lost * topo.d_accept_ms
    accept = proposal + accept_delay

    # Storage commit: latency inflates once the node is busy.
    busy = np.clip(
        (exe.t_block_fixed_ms + n_in_block * exe.t_exec_ms)
        / np.maximum(block_ms, 1e-9),
        0.0,
        4.0,
    )
    inflation = 1.0 + np.clip(busy - exe.commit_knee, 0.0, None) ** 2 * 3.0
    commit_ms = (
        exe.t_commit_ms
        * inflation
        * _lognormal_factor(rng, exe.commit_sigma, n_blocks)
    )
    commit = accept + commit_ms

    block_of = np.empty(n_tx, dtype=np.int64)
    block_of[order] = block_of_sorted
    return block_of, proposal, accept, commit, n_in_block, commit_ms, busy


def simulate_run(
    spec: RunSpec, seed: Optional[int] = None
) -> Dict[str, object]:
    """Simulate one run and return records, telemetry and the passport."""
    topo = TOPOLOGY_MODELS[spec.topology]
    block_ms = block_target_ms(spec.config)
    exe = EXECUTION

    if seed is None:
        seed = derive_seed("run", spec.run_id, spec.config, spec.topology,
                           spec.load_tps, spec.repeat)
    rng = np.random.default_rng(seed)

    # ---- arrivals -------------------------------------------------------
    trace = build_trace(
        TraceSpec(spec.load_tps, spec.repeat, spec.measure_s)
    )
    warm = build_trace(
        TraceSpec(spec.load_tps, 100 + spec.repeat, spec.warmup_s)
    )

    t_send_ms = np.concatenate(
        [
            warm.t_offset_s.to_numpy() * 1000.0,
            trace.t_offset_s.to_numpy() * 1000.0 + spec.warmup_s * 1000.0,
        ]
    )
    is_measure = np.concatenate(
        [np.zeros(len(warm), dtype=bool), np.ones(len(trace), dtype=bool)]
    )
    seq = np.concatenate([warm.seq.to_numpy(), trace.seq.to_numpy()])
    client = np.concatenate([warm.client_id.to_numpy(), trace.client_id.to_numpy()])
    key_hex = np.concatenate([warm.key_hex.to_numpy(), trace.key_hex.to_numpy()])
    n_tx = t_send_ms.size

    # ---- ingress: RPC leg plus gossip to the proposer --------------------
    ingress = (topo.d_client_write_ms + topo.d_gossip_ms) * _lognormal_factor(
        rng, topo.jitter_sigma, n_tx
    )
    t_ready_ms = t_send_ms + ingress

    # Operating point of the node: consensus work from the block cadence
    # plus execution work from the offered load.
    pressure = cpu_pressure(1000.0 / block_ms, float(spec.load_tps))
    slow_scale = slow_round_scale(pressure)

    horizon_ms = (spec.warmup_s + spec.measure_s + spec.drain_s) * 1000.0
    (
        block_of,
        proposal,
        accept,
        commit,
        n_in_block,
        commit_ms,
        busy,
    ) = _simulate_blocks(
        t_ready_ms, block_ms, horizon_ms, rng, topo, exe, slow_scale=slow_scale
    )

    included = block_of >= 0
    b = np.where(included, block_of, 0)

    # ---- receipt discovery on the client polling grid ---------------------
    poll_ms = POLL_S * 1000.0
    receipt_avail = commit[b] + topo.d_client_write_ms  # response leg
    j_receipt = np.ceil(
        (receipt_avail - topo.d_client_write_ms - t_send_ms) / poll_ms
    )
    j_receipt = np.maximum(j_receipt, 1.0)
    t_receipt_ms = t_send_ms + j_receipt * poll_ms + 2.0 * topo.d_client_write_ms

    # ---- confirmed read on each independent read node ---------------------
    read_names = list(READ_NODES)
    t_read_ms = np.empty((len(read_names), n_tx), dtype=np.float64)
    for ri, _name in enumerate(read_names):
        asymmetry = 1.0 if ri == 0 else topo.read_asymmetry
        apply_delay = topo.d_apply_ms * asymmetry * _lognormal_factor(
            rng, topo.jitter_sigma, proposal.size
        )
        state_visible = accept + apply_delay + commit_ms
        target = state_visible[b]
        j_read = np.ceil(
            (target - topo.d_client_read_ms - t_receipt_ms) / poll_ms
        )
        j_read = np.maximum(j_read, 0.0)
        t_read_ms[ri] = (
            t_receipt_ms + j_read * poll_ms + 2.0 * topo.d_client_read_ms
        )

    t_visible_first = t_read_ms.min(axis=0) - t_send_ms   # equation (5)
    t_visible_all = t_read_ms.max(axis=0) - t_send_ms     # equation (6)
    t_convergence = t_read_ms.max(axis=0) - t_read_ms.min(axis=0)  # equation (7)

    # ---- status classification -------------------------------------------
    timeout_ms = TIMEOUT_S * 1000.0
    status = np.where(
        ~included, "timeout",
        np.where(t_visible_all > timeout_ms, "timeout", "success"),
    )
    error_class = np.where(
        status == "timeout",
        np.where(~included, "not_included", "state_visibility_timeout"),
        "",
    )

    # ---- keep only the measurement window ---------------------------------
    m = is_measure
    records = pd.DataFrame(
        {
            "run_id": spec.run_id,
            "config": spec.config,
            "topology": spec.topology,
            "load_tps": spec.load_tps,
            "repeat": spec.repeat,
            "trace_id": spec.trace_id,
            "client_id": client[m],
            "seq": seq[m],
            "key_hex": key_hex[m],
            "t_send_ns": (t_send_ms[m] * 1e6 + _CLOCK_BASE_NS).astype(np.int64),
            "t_hash_ns": (
                (t_send_ms[m] + 2.0 * topo.d_client_write_ms) * 1e6 + _CLOCK_BASE_NS
            ).astype(np.int64),
            "t_receipt_ns": (
                t_receipt_ms[m] * 1e6 + _CLOCK_BASE_NS
            ).astype(np.int64),
            "t_visible_first_ms": t_visible_first[m],
            "t_visible_all_ms": t_visible_all[m],
            "t_convergence_ms": t_convergence[m],
            "block_number": np.where(included, b, -1)[m],
            "block_time_ms": np.where(included, proposal[b], np.nan)[m],
            "status": status[m],
            "error_class": error_class[m],
            "payload_bytes": 132,
            "gas_used": exe.gas_per_tx,
            "provenance": PROVENANCE_SIMULATED,
        }
    )
    for ri, name in enumerate(read_names):
        records[f"t_read_{name}_ns"] = (
            t_read_ms[ri][m] * 1e6 + _CLOCK_BASE_NS
        ).astype(np.int64)

    # Pseudonymised account token and deterministic transaction hash.
    salt = f"{spec.run_id}:{spec.trace_id}"
    records["account_token"] = [
        hashlib.blake2b(f"{salt}|{c}".encode(), digest_size=8).hexdigest()
        for c in records.client_id
    ]
    records["tx_hash"] = [
        "0x" + hashlib.blake2b(f"{salt}|{s}".encode(), digest_size=32).hexdigest()
        for s in records.seq
    ]
    records.loc[~np.asarray(included)[m], ["block_time_ms"]] = np.nan

    # ---- run-level telemetry ---------------------------------------------
    blocks = _block_frame(spec, proposal, accept, n_in_block, commit_ms, block_ms)
    resources = _resource_frame(spec, proposal, n_in_block, t_ready_ms, block_of,
                                commit_ms, rng, block_ms)
    probes = _network_probes(spec, topo, rng)

    passport = {
        "run_id": spec.run_id,
        "config": spec.config,
        "topology": spec.topology,
        "load_tps": spec.load_tps,
        "repeat": spec.repeat,
        "trace_id": spec.trace_id,
        "trace_sha256": trace_sha256(trace),
        "warmup_s": spec.warmup_s,
        "measure_s": spec.measure_s,
        "drain_s": spec.drain_s,
        "seed": int(seed),
        "block_target_ms": block_ms,
        "cpu_pressure": float(pressure),
        "slow_round_scale": float(slow_scale),
        "n_scheduled_tx": int(m.sum()),
        "n_blocks": int(proposal.size),
        "provenance": PROVENANCE_SIMULATED,
        "generator": f"alp.simulate {__version__}",
        "model": model_manifest(),
        "data_required": (
            "Replace with the real run passport: node inventory, NodeIDs, "
            "AvalancheGo/Subnet-EVM versions, genesis and contract hashes, "
            "clock offset, measured RTT matrix."
        ),
    }
    return {
        "records": records,
        "blocks": blocks,
        "resources": resources,
        "probes": probes,
        "passport": passport,
    }


def _block_frame(spec, proposal, accept, n_in_block, commit_ms, block_ms):
    interval = np.diff(proposal, prepend=proposal[0] - block_ms)
    return pd.DataFrame(
        {
            "run_id": spec.run_id,
            "block_number": np.arange(proposal.size, dtype=np.int64),
            "t_proposal_ms": proposal,
            "t_accept_ms": accept,
            "n_tx": n_in_block,
            "interval_ms": interval,
            "commit_ms": commit_ms,
        }
    )


def _resource_frame(spec, proposal, n_in_block, t_ready_ms, block_of, commit_ms,
                    rng, block_ms, exe=EXECUTION):
    """One-second node telemetry: CPU, memory, disk and queue depth."""
    horizon_s = spec.warmup_s + spec.measure_s + spec.drain_s
    edges = np.arange(0.0, horizon_s * 1000.0 + 1.0, 1000.0)
    bin_of_block = np.clip(
        np.searchsorted(edges, proposal, side="right") - 1, 0, len(edges) - 2
    )
    n_bins = len(edges) - 1

    cpu_ms = np.zeros(n_bins)
    np.add.at(
        cpu_ms,
        bin_of_block,
        exe.cpu_ms_per_block + n_in_block * exe.cpu_ms_per_tx,
    )
    cpu_pct = exe.cpu_idle_pct + 100.0 * cpu_ms / (1000.0 * exe.cpu_cores)
    cpu_pct = np.clip(cpu_pct + rng.normal(0.0, 1.1, n_bins), 0.0, 100.0)

    # Queue depth: ready but not yet included, sampled once per second.
    included_at = np.where(block_of >= 0, proposal[np.clip(block_of, 0, None)], np.inf)
    centres = edges[:-1] + 500.0
    ready_sorted = np.sort(t_ready_ms)
    incl_sorted = np.sort(included_at)
    arrived = np.searchsorted(ready_sorted, centres, side="right")
    served = np.searchsorted(incl_sorted, centres, side="right")
    queue_depth = np.maximum(arrived - served, 0)

    disk_p99 = np.full(n_bins, np.nan)
    for i in range(n_bins):
        sel = bin_of_block == i
        if sel.any():
            disk_p99[i] = float(np.quantile(commit_ms[sel], 0.99))
    mem = exe.mem_base_mib + queue_depth * exe.mem_per_queued_mib * 1024.0

    return pd.DataFrame(
        {
            "run_id": spec.run_id,
            "t_s": np.arange(n_bins),
            "phase": np.where(
                np.arange(n_bins) < spec.warmup_s,
                "warmup",
                np.where(
                    np.arange(n_bins) < spec.warmup_s + spec.measure_s,
                    "measure",
                    "drain",
                ),
            ),
            "cpu_pct": cpu_pct,
            "mem_mib": mem,
            "disk_p99_ms": disk_p99,
            "queue_depth": queue_depth,
            "blocks_per_s": np.bincount(bin_of_block, minlength=n_bins),
        }
    )


def _network_probes(spec, topo, rng):
    """Active RTT/jitter/loss probes taken before, during and after a run."""
    out = []
    base_rtt = 2.0 * (topo.d_gossip_ms + topo.d_apply_ms)
    for phase in ("before", "during", "after"):
        out.append(
            {
                "run_id": spec.run_id,
                "phase": phase,
                "rtt_ms_mean": float(base_rtt * (1.0 + rng.normal(0, 0.02))),
                "jitter_ms": float(base_rtt * topo.jitter_sigma * 0.25),
                "loss_pct": float(topo.loss_frac * 100.0),
                "netem": topo.netem_note,
                "provenance": PROVENANCE_SIMULATED,
            }
        )
    return out


# --------------------------------------------------------------------------
# Campaign driver
# --------------------------------------------------------------------------

def run_campaign(
    profile: CampaignProfile | str,
    schedule: pd.DataFrame,
    out_root: Path,
    progress: bool = True,
) -> pd.DataFrame:
    """Simulate every run of ``schedule`` and write the raw dataset.

    Layout follows protocol section 10::

        data/raw/tx/<run_id>.jsonl.gz     transaction records
        data/raw/nodes/<run_id>_blocks.csv
        data/raw/nodes/<run_id>_resources.csv
        data/raw/network/<run_id>_probes.json
        data/raw/manifests/<run_id>.json  run passport
    """
    if isinstance(profile, str):
        profile = get_profile(profile)
    out_root = Path(out_root)
    for sub in ("tx", "nodes", "network", "manifests"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    index_rows = []
    total = len(schedule)
    for i, row in enumerate(schedule.itertuples(index=False), start=1):
        spec = RunSpec(
            run_id=row.run_id,
            config=row.config,
            topology=row.topology,
            load_tps=int(row.load_tps),
            repeat=int(row.repeat),
            trace_id=row.trace_id,
            measure_s=profile.measure_s,
            warmup_s=profile.warmup_s,
            drain_s=profile.drain_s,
        )
        result = simulate_run(spec)
        write_run(result, out_root)
        rec = result["records"]
        index_rows.append(
            {
                "run_id": spec.run_id,
                "config": spec.config,
                "topology": spec.topology,
                "load_tps": spec.load_tps,
                "repeat": spec.repeat,
                "trace_id": spec.trace_id,
                "n_records": len(rec),
                "n_success": int((rec.status == "success").sum()),
                "provenance": PROVENANCE_SIMULATED,
            }
        )
        if progress and (i % 25 == 0 or i == total):
            print(f"  simulated {i}/{total} runs", flush=True)

    index = pd.DataFrame(index_rows)
    index.to_csv(out_root / "run_index.csv", index=False, lineterminator="\n")
    return index


def write_run(result: Dict[str, object], out_root: Path) -> None:
    """Persist one simulated run in the protocol's directory layout."""
    out_root = Path(out_root)
    run_id = result["passport"]["run_id"]

    records: pd.DataFrame = result["records"]
    path = out_root / "tx" / f"{run_id}.jsonl.gz"
    payload = "".join(
        json.dumps(rec, separators=(",", ":"), default=_json_default) + "\n"
        for rec in records.to_dict(orient="records")
    ).encode("utf-8")
    # mtime=0 keeps the archive byte-reproducible across regenerations.
    with open(path, "wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
            gz.write(payload)

    result["blocks"].to_csv(
        out_root / "nodes" / f"{run_id}_blocks.csv", index=False,
        lineterminator="\n", float_format="%.6f",
    )
    result["resources"].to_csv(
        out_root / "nodes" / f"{run_id}_resources.csv", index=False,
        lineterminator="\n", float_format="%.6f",
    )
    (out_root / "network" / f"{run_id}_probes.json").write_text(
        json.dumps(result["probes"], indent=2) + "\n", encoding="utf-8"
    )
    (out_root / "manifests" / f"{run_id}.json").write_text(
        json.dumps(result["passport"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"unserialisable value of type {type(value)!r}")
