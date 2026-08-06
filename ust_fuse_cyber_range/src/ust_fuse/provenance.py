"""Reproducibility & provenance manifest (ЛР-8, ЛР-10).

Every accepted result must run "з контейнера та маніфесту" (KPI, section 13).
This module builds a manifest capturing the experiment id, seed, config hash,
package versions, environment and content checksums, so a figure can be traced
back to the RAW data that produced it.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict


def stable_hash(obj: Any) -> str:
    """Deterministic short hash of a JSON-serialisable object."""
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_versions() -> Dict[str, str]:
    versions = {"python": sys.version.split()[0]}
    for name in ("numpy", "scipy", "matplotlib", "pandas", "yaml"):
        try:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", "unknown")
        except Exception:
            versions[name] = "not-installed"
    return versions


@dataclass
class Manifest:
    experiment_id: str
    scenario_id: str
    seed: int
    config_hash: str
    created_at: str
    environment: Dict[str, str] = field(default_factory=dict)
    packages: Dict[str, str] = field(default_factory=dict)
    checksums: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return dict(self.__dict__)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


def build_manifest(config_dict: Dict, seed: int, scenario_id: str,
                   created_epoch: float | None = None) -> Manifest:
    # config_hash identifies the experimental *setup* and is seed-independent, so
    # the same range/scenario yields the same config hash across seeds; the seed
    # is folded only into the experiment id.
    setup = {k: v for k, v in config_dict.items() if k != "seed"}
    cfg_hash = stable_hash(setup)
    # deterministic experiment id from config + seed (reproducible, no wall clock)
    exp_id = stable_hash({"cfg": cfg_hash, "seed": seed, "scn": scenario_id})
    created = created_epoch if created_epoch is not None else 0.0
    created_str = (
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created))
        if created_epoch is not None else "deterministic"
    )
    env = {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python_impl": platform.python_implementation(),
    }
    return Manifest(
        experiment_id=f"EXP-{exp_id}",
        scenario_id=scenario_id,
        seed=seed,
        config_hash=cfg_hash,
        created_at=created_str,
        environment=env,
        packages=package_versions(),
    )
