"""Identifier generation.

Two rules govern every identifier in the release:

1. An identifier must carry no information. ``event_id`` must not encode a site,
   a time, or a participant, because a structured key leaks exactly the
   attributes the generalization step removes.
2. An identifier must be reproducible. A pipeline re-run over the same inputs
   with the same release salt must produce the same keys, otherwise provenance
   relations and split manifests cannot be compared across versions.

These pull in opposite directions, and the resolution is a keyed hash: the id is
a deterministic function of the source key and a secret release salt, so it is
stable across runs but not invertible or linkable without the salt. The salt
lives in the controlled tier and is never written to the open package.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from typing import Iterable

NAMESPACE = uuid.UUID("6f0f3d2a-2b3c-4f1e-9a55-0c7d4b8e1a90")


def release_salt(seed: str) -> bytes:
    """Derive the per-release salt from a secret seed.

    In production the seed is read from a secret store. It is passed explicitly
    here so that no module reaches for ambient state.
    """
    return hashlib.sha256(("uavews-release-salt::" + seed).encode("utf-8")).digest()


def keyed_uuid(salt: bytes, *parts: object) -> str:
    """Deterministic, non-invertible UUID for a tuple of source key parts."""
    msg = "\x1f".join(str(p) for p in parts).encode("utf-8")
    digest = hmac.new(salt, msg, hashlib.sha256).digest()
    return str(uuid.UUID(bytes=digest[:16], version=4))


def event_id(salt: bytes, campaign: str, run: object) -> str:
    return keyed_uuid(salt, "event", campaign, run)


def window_id(salt: bytes, event: str, index: int) -> str:
    return keyed_uuid(salt, "window", event, index)


def observation_id(salt: bytes, source: str, native_key: object) -> str:
    return keyed_uuid(salt, "observation", source, native_key)


def object_id(salt: bytes, source: str, native_key: object) -> str:
    return keyed_uuid(salt, "object", source, native_key)


def label_id(salt: bytes, target_kind: str, target: str, annotator: str) -> str:
    return keyed_uuid(salt, "label", target_kind, target, annotator)


def activity_id(salt: bytes, activity: str, subject: object) -> str:
    return keyed_uuid(salt, "activity", activity, subject)


def rotating_source_id(salt: bytes, contributor_key: str, epoch: int) -> str:
    """Pseudonymous source id that changes every rotation epoch.

    ``epoch`` is floor(days_since_collection_start / rotation_policy_days). Two
    contributions from one device in different epochs are unlinkable in the open
    tier; within an epoch they stay linkable, which is required so that repeated
    reports from one device are clustered rather than counted as independent
    corroboration.
    """
    return keyed_uuid(salt, "source", contributor_key, epoch)


def source_event_id_hash(salt: bytes, native_id: str) -> str:
    """Hash of an upstream operational identifier.

    The raw identifier never enters the repository; the hash is retained so that
    a duplicate delivery of the same upstream event can still be detected.
    """
    return hmac.new(salt, native_id.encode("utf-8"), hashlib.sha256).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def group_key(salt: bytes, members: Iterable[str]) -> str:
    """Stable key for an unordered group (near-duplicate cluster, route family)."""
    return keyed_uuid(salt, "group", "|".join(sorted(members)))
