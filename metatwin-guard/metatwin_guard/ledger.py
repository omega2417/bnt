"""QuorumEvidenceLedger: single-process emulation of a quorum-signed,
hash-chained evidence structure (Section 3.8).

It is NOT a distributed blockchain: all validator keys live in one process,
there is no peer-to-peer protocol, consensus, replication or persistence.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import config
from .crypto import GENESIS_HASH, deterministic_private_key, hash_obj, sign_hex, verify_hex


@dataclass
class VerifyReport:
    valid: bool
    n_blocks: int
    errors: list[str]


@dataclass
class QuorumEvidenceLedger:
    seed: int = config.MASTER_SEED
    n_validators: int = config.N_VALIDATORS
    quorum: int = config.QUORUM
    blocks: list[dict[str, Any]] = field(default_factory=list)
    append_times_ms: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._keys = {
            f"validator-{i}": deterministic_private_key(f"validator-{i}", self.seed)
            for i in range(1, self.n_validators + 1)
        }
        self.validator_registry: dict[str, Ed25519PublicKey] = {
            vid: k.public_key() for vid, k in self._keys.items()
        }

    @property
    def head_hash(self) -> str:
        return self.blocks[-1]["block_hash"] if self.blocks else GENESIS_HASH

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter()
        body = {
            "index": len(self.blocks),
            "previous_block_hash": self.head_hash,
            **record,
        }
        block_hash = hash_obj(body)
        sigs = {vid: sign_hex(k, bytes.fromhex(block_hash)) for vid, k in self._keys.items()}
        block = {"body": body, "block_hash": block_hash, "signatures": sigs}
        self.blocks.append(block)
        self.append_times_ms.append((time.perf_counter() - t0) * 1000.0)
        return block

    def _valid_signatures(self, signatures: dict[str, str], block_hash: str) -> int:
        """Counts valid registered signatures, stopping once the quorum is reached."""
        message = bytes.fromhex(block_hash)
        valid = 0
        for vid, sig in signatures.items():
            pub = self.validator_registry.get(vid)
            if pub is not None and isinstance(sig, str) and verify_hex(pub, sig, message):
                valid += 1
                if valid >= self.quorum:
                    break
        return valid

    def verify(self) -> VerifyReport:
        errors: list[str] = []
        prev = GENESIS_HASH
        for i, b in enumerate(self.blocks):
            try:
                body = b["body"]
                if body.get("index") != i:
                    errors.append(f"block {i}: index mismatch")
                if body.get("previous_block_hash") != prev:
                    errors.append(f"block {i}: previous-block hash mismatch")
                recomputed = hash_obj(body)
                if recomputed != b["block_hash"]:
                    errors.append(f"block {i}: body hash mismatch")
                valid_sigs = self._valid_signatures(b["signatures"], recomputed)
                if valid_sigs < self.quorum:
                    errors.append(f"block {i}: {valid_sigs}/{self.n_validators} valid signatures < quorum {self.quorum}")
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                errors.append(f"block {i}: malformed ({type(exc).__name__})")
            prev = b.get("block_hash") if isinstance(b, dict) else None
        return VerifyReport(not errors, len(self.blocks), errors)

    def tampered_copy(self) -> "QuorumEvidenceLedger":
        """Deep copy for tamper experiments that keeps the validator registry."""
        other = copy.copy(self)
        other.blocks = copy.deepcopy(self.blocks)
        other.append_times_ms = list(self.append_times_ms)
        return other
