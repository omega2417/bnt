"""Config loading, run manifests and reproducibility bookkeeping.

Requirement (prompt §Обмеження.7): every run carries a run_id, timestamp, git
commit, config hash, environment manifest, seed and output directory.  All of
that is assembled here so the rest of the code never hand-rolls it.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from .schemas import (
    AttackConfig,
    ExperimentConfig,
    ScenarioConfig,
)

T = TypeVar("T", bound=BaseModel)

__all__ = [
    "load_yaml",
    "load_model",
    "load_scenario",
    "load_attack",
    "load_experiment",
    "config_hash",
    "RunManifest",
    "project_root",
]


def project_root() -> Path:
    """Return the repository root (directory containing ``configs/``)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "configs").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    # Fallback: two levels up from src/aegis_uav/
    return here.parents[2]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    root = project_root()
    if (root / p).exists():
        return root / p
    return p


def load_yaml(path: str | Path) -> dict[str, Any]:
    resolved = _resolve(path)
    with open(resolved) as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {resolved}, got {type(data)}")
    return data


def load_model(model_cls: type[T], path: str | Path) -> T:
    """Load a YAML file into a pydantic model of type ``model_cls``."""
    return model_cls.model_validate(load_yaml(path))


def load_scenario(path: str | Path) -> ScenarioConfig:
    return load_model(ScenarioConfig, path)


def load_attack(path: str | Path) -> AttackConfig:
    data = load_yaml(path)
    # Attack YAMLs are nested under an "attack:" key per the prompt example.
    if "attack" in data:
        data = data["attack"]
    return AttackConfig.model_validate(data)


def load_experiment(path: str | Path) -> ExperimentConfig:
    return load_model(ExperimentConfig, path)


def config_hash(*objs: Any) -> str:
    """Stable short hash over one or more (JSON-serialisable) config objects."""
    parts: list[str] = []
    for obj in objs:
        if isinstance(obj, BaseModel):
            parts.append(obj.model_dump_json())
        else:
            parts.append(json.dumps(obj, sort_keys=True, default=str))
    blob = "\x1f".join(parts).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root(),
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # pragma: no cover - git may be absent
        pass
    return "unknown"


def _environment_manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
    }
    for pkg in ("numpy", "pandas", "scipy", "sklearn", "matplotlib", "pydantic"):
        try:
            module = __import__(pkg)
            manifest[f"{pkg}_version"] = getattr(module, "__version__", "unknown")
        except Exception:  # pragma: no cover
            manifest[f"{pkg}_version"] = "not-installed"
    return manifest


@dataclass
class RunManifest:
    """Reproducibility record written next to every run's artifacts."""

    run_id: str
    run_group: str
    seed: int
    config_hash: str
    timestamp: str
    output_dir: Path
    git_commit: str = field(default_factory=_git_commit)
    environment: dict[str, Any] = field(default_factory=_environment_manifest)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        run_group: str,
        seed: int,
        cfg_hash: str,
        output_root: Path,
        timestamp: str,
        label: str | None = None,
    ) -> RunManifest:
        run_id = f"{run_group}-{label + '-' if label else ''}s{seed}-{cfg_hash}"
        output_dir = output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            run_id=run_id,
            run_group=run_group,
            seed=seed,
            config_hash=cfg_hash,
            timestamp=timestamp,
            output_dir=output_dir,
        )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "run_id": self.run_id,
            "run_group": self.run_group,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "timestamp": self.timestamp,
            "git_commit": self.git_commit,
            "output_dir": str(self.output_dir),
            "environment": self.environment,
            "extra": self.extra,
        }
        return d

    def save(self) -> Path:
        path = self.output_dir / "run_manifest.json"
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)
        return path
