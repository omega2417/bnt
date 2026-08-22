"""Client-side measurement core for a real campaign (protocol Listing 5).

This is the module that runs on the 25 Kali Linux workstations.  It is
deliberately separate from :mod:`alp.simulate`: it produces records in the
identical schema, labelled ``MEASURED``, so :mod:`alp.analyze` consumes
them without a single change.

Two properties matter for correctness of the primary metric.

* **Open loop.**  ``submit_one`` blocks until the state is visible, so it
  cannot pace itself.  The dispatcher fires transactions on the timestamps
  of the immutable trace from a thread pool; a slow response delays that
  transaction's result, never the offered load.  A closed loop would turn
  an overload into an artificially polite arrival process and hide exactly
  the queueing behaviour the study is about.
* **One clock.**  Every timestamp of a transaction comes from the
  generator's ``time.perf_counter_ns``.  Differences are therefore free of
  inter-host clock offset; NTP/chrony discipline is still recorded in the
  run passport, but the primary metric does not depend on it.

``web3`` is imported lazily so that the analysis pipeline, the tests and
the Colab notebook do not need an Ethereum client library installed.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from . import PROVENANCE_MEASURED
from .config import POLL_S, TIMEOUT_S


@dataclass
class ClientConfig:
    """Everything one workstation needs to execute one run."""

    write_rpc: str
    read_rpcs: Sequence[str]
    read_names: Sequence[str]
    contract: str
    abi: list
    private_key: str
    run_id: str
    config: str
    topology: str
    load_tps: int
    repeat: int
    trace_id: str
    client_id: str
    out_path: Path
    poll_s: float = POLL_S
    timeout_s: float = TIMEOUT_S
    gas: int = 120_000
    max_workers: int = 64

    @classmethod
    def from_env(cls, out_path: Optional[Path] = None) -> "ClientConfig":
        """Build the configuration from the environment of the run harness.

        Private keys arrive through the environment or a secret store and
        are never written to JSONL, to Git or to the published dataset.
        """
        read_rpcs = os.environ["RPC_READS"].split(",")
        read_names = os.environ.get(
            "READ_NODE_NAMES", ",".join(f"R{i + 1}" for i in range(len(read_rpcs)))
        ).split(",")
        run_id = os.environ["RUN_ID"]
        return cls(
            write_rpc=os.environ["RPC_WRITE"],
            read_rpcs=read_rpcs,
            read_names=read_names,
            contract=os.environ["PROBE_CONTRACT"],
            abi=json.loads(os.environ["PROBE_ABI_JSON"]),
            private_key=os.environ["EVM_PRIVATE_KEY"],
            run_id=run_id,
            config=os.environ["CONFIG"],
            topology=os.environ["TOPOLOGY"],
            load_tps=int(os.environ["LOAD_TPS"]),
            repeat=int(os.environ["REPEAT"]),
            trace_id=os.environ["TRACE_ID"],
            client_id=os.environ["CLIENT_ID"],
            out_path=Path(out_path or os.environ.get("OUT_JSONL", f"{run_id}.jsonl")),
        )


class JsonlWriter:
    """Append-only, fsync-ed, thread-safe record sink."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: Dict[str, object]) -> None:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())


class NonceAllocator:
    """Conflict-free local nonce source for one account.

    Each workstation owns one EVM account, so nonces can be handed out
    locally.  A gap caused by a rejected transaction is repaired by
    resynchronising against the node's pending count.
    """

    def __init__(self, w3, address: str):
        self._w3 = w3
        self._address = address
        self._lock = threading.Lock()
        self._next = w3.eth.get_transaction_count(address, "pending")

    def take(self) -> int:
        with self._lock:
            value = self._next
            self._next += 1
            return value

    def resync(self) -> None:
        with self._lock:
            self._next = self._w3.eth.get_transaction_count(self._address, "pending")


class ProbeClient:
    """Measures one transaction from submission to confirmed read."""

    def __init__(self, cfg: ClientConfig):
        from web3 import Web3  # imported lazily; see the module docstring
        from eth_account import Account

        self.cfg = cfg
        self.w3 = Web3(Web3.HTTPProvider(cfg.write_rpc, request_kwargs={"timeout": 10}))
        self.readers = [
            Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 10}))
            for url in cfg.read_rpcs
        ]
        self.account = Account.from_key(cfg.private_key)
        self.address = Web3.to_checksum_address(cfg.contract)
        self.probe = self.w3.eth.contract(address=self.address, abi=cfg.abi)
        self.reader_probes = [
            r.eth.contract(address=self.address, abi=cfg.abi) for r in self.readers
        ]
        self.nonces = NonceAllocator(self.w3, self.account.address)
        self.chain_id = self.w3.eth.chain_id
        self.writer = JsonlWriter(cfg.out_path)
        self._pool = ThreadPoolExecutor(max_workers=max(len(self.readers), 2))

    # -- timing helpers --------------------------------------------------
    @staticmethod
    def now_ns() -> int:
        return time.perf_counter_ns()

    def _wait_receipt(self, tx_hash, deadline: float):
        from web3.exceptions import TransactionNotFound

        while time.monotonic() < deadline:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                return receipt, self.now_ns()
            except TransactionNotFound:
                pass
            time.sleep(self.cfg.poll_s)
        raise TimeoutError("receipt timeout")

    def _wait_state(self, index: int, key: bytes, expected_seq: int, deadline: float):
        """Poll one read node until it returns a sequence >= expected."""
        probe = self.reader_probes[index]
        while time.monotonic() < deadline:
            value, seq = probe.functions.read(key).call(block_identifier="latest")
            if seq >= expected_seq:
                return self.now_ns(), int(value), int(seq)
            time.sleep(self.cfg.poll_s)
        raise TimeoutError("state visibility timeout")

    # -- one transaction --------------------------------------------------
    def submit_one(self, key_hex: str, value: int, seq: int) -> Dict[str, object]:
        cfg = self.cfg
        key = bytes.fromhex(key_hex.removeprefix("0x"))
        base = {
            "run_id": cfg.run_id,
            "config": cfg.config,
            "topology": cfg.topology,
            "load_tps": cfg.load_tps,
            "repeat": cfg.repeat,
            "trace_id": cfg.trace_id,
            "client_id": cfg.client_id,
            "seq": seq,
            "key_hex": key_hex,
            "provenance": PROVENANCE_MEASURED,
        }
        deadline = time.monotonic() + cfg.timeout_s
        try:
            gas_price = self.w3.eth.gas_price
            tx = self.probe.functions.write(key, value, seq).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.nonces.take(),
                    "chainId": self.chain_id,
                    "gas": cfg.gas,
                    "maxFeePerGas": 2 * gas_price,
                    "maxPriorityFeePerGas": min(gas_price, 2_000_000_000),
                }
            )
            signed = self.account.sign_transaction(tx)
            t_send = self.now_ns()
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            t_hash = self.now_ns()

            receipt, t_receipt = self._wait_receipt(tx_hash, deadline)
            base.update(
                tx_hash=tx_hash.hex(),
                t_send_ns=t_send,
                t_hash_ns=t_hash,
                t_receipt_ns=t_receipt,
                block_number=int(receipt.blockNumber),
                gas_used=int(receipt.gasUsed),
                payload_bytes=len(signed.raw_transaction),
            )
            if receipt.status != 1:
                base.update(status="revert", error_class="revert")
                return base

            # Poll every read node concurrently.  Sequential polling would
            # bias T_visible,all by at least one polling interval per node.
            results = list(
                self._pool.map(
                    lambda i: self._wait_state(i, key, seq, deadline),
                    range(len(self.readers)),
                )
            )
            reads = [r[0] for r in results]
            observed = {(r[1], r[2]) for r in results}
            base.update(
                {f"t_read_{name}_ns": t for name, t in zip(cfg.read_names, reads)}
            )
            base.update(
                t_visible_first_ms=(min(reads) - t_send) / 1e6,
                t_visible_all_ms=(max(reads) - t_send) / 1e6,
                t_convergence_ms=(max(reads) - min(reads)) / 1e6,
                status="success",
                error_class="" if len(observed) == 1 else "read_mismatch",
            )
            return base
        except TimeoutError as exc:
            self.nonces.resync()
            base.update(status="timeout", error_class=str(exc))
            return base
        except Exception as exc:  # noqa: BLE001 - every failure stays in the denominator
            self.nonces.resync()
            base.update(status="error", error_class=f"{type(exc).__name__}: {exc}")
            return base

    def close(self) -> None:
        self._pool.shutdown(wait=True)


def run_open_loop(
    cfg: ClientConfig,
    trace: "Sequence[Dict[str, object]]",
    phase_filter: Optional[Callable[[Dict[str, object]], bool]] = None,
) -> int:
    """Replay a trace open-loop and write one JSONL record per transaction.

    ``trace`` rows carry ``t_offset_s``, ``seq``, ``key_hex`` and ``value``
    for this client only.  Records whose ``phase_filter`` returns ``False``
    (the warm-up) are executed but not written.
    """
    client = ProbeClient(cfg)
    results: "queue.Queue[Dict[str, object]]" = queue.Queue()
    stop = threading.Event()

    def drain():
        while not (stop.is_set() and results.empty()):
            try:
                record = results.get(timeout=0.2)
            except queue.Empty:
                continue
            if phase_filter is None or phase_filter(record):
                client.writer.append(record)

    writer_thread = threading.Thread(target=drain, daemon=True)
    writer_thread.start()

    written = 0
    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        start = time.monotonic()
        for row in trace:
            due = start + float(row["t_offset_s"])
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            pool.submit(
                lambda r=row: results.put(
                    client.submit_one(r["key_hex"], int(r["value"]), int(r["seq"]))
                )
            )
            written += 1
    stop.set()
    writer_thread.join(timeout=cfg.timeout_s + 5)
    client.close()
    return written


def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - field entry
    """Entry point used on the workstations: ``python -m alp.client trace.csv``."""
    import argparse

    import pandas as pd

    parser = argparse.ArgumentParser(description="VisibilityProbe measurement client")
    parser.add_argument("trace", help="CSV trace slice for this client")
    parser.add_argument("--out", default=None, help="output JSONL path")
    parser.add_argument("--warmup-s", type=float, default=0.0,
                        help="leading seconds executed but excluded from the output")
    args = parser.parse_args(argv)

    cfg = ClientConfig.from_env(Path(args.out) if args.out else None)
    trace = pd.read_csv(args.trace).to_dict(orient="records")
    warmup = args.warmup_s

    def keep(record: Dict[str, object]) -> bool:
        return True if warmup <= 0 else record.get("phase", "measure") != "warmup"

    n = run_open_loop(cfg, trace, keep)
    print(f"{cfg.run_id}: dispatched {n} transactions -> {cfg.out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
