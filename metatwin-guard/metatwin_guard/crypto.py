"""Canonical encoding, SHA-256 hashing and Ed25519 signatures.

SHA-256: FIPS PUB 180-4, doi:10.6028/NIST.FIPS.180-4
Ed25519: RFC 8032, doi:10.17487/RFC8032
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8, finite floats."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


def deterministic_private_key(label: str, seed: int) -> Ed25519PrivateKey:
    """TEST FIXTURE ONLY. Derives a reproducible key from a label and seed.

    These keys make the synthetic benchmark reproducible. They must never be
    reused in a field deployment (Section 3.4).
    """
    material = hashlib.sha256(f"metatwin-guard/test-key/{seed}/{label}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(material)


def public_key_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def sign_hex(key: Ed25519PrivateKey, message: bytes) -> str:
    return key.sign(message).hex()


def verify_hex(pub: Ed25519PublicKey, signature_hex: str, message: bytes) -> bool:
    try:
        pub.verify(bytes.fromhex(signature_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
