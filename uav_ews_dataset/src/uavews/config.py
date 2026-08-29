"""Loading and validation of release parameters and controlled vocabularies.

Nothing in the pipeline hard-codes a threshold. Every release-specific number
lives in ``config/pipeline.yaml`` so that a run is reproducible from a single
artefact, and so that the value written into the validation report and the value
quoted in the manuscript cannot drift apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

PKG_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PKG_ROOT / "config" / "pipeline.yaml"
DEFAULT_VOCAB = PKG_ROOT / "config" / "vocabularies.yaml"


class ConfigError(ValueError):
    """Raised when the configuration is internally inconsistent."""


@dataclass(frozen=True)
class Config:
    """Parsed pipeline configuration plus the derived quantities it implies."""

    raw: Dict[str, Any]
    vocab: Dict[str, Any]
    source_path: Path

    # -- convenience accessors -------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def release(self) -> Dict[str, Any]:
        return self.raw["release"]

    @property
    def zone_polygon(self) -> List[List[float]]:
        return self.raw["zone"]["polygon_en_m"]

    @property
    def delta_t_s(self) -> float:
        return float(self.raw["kinematics"]["delta_t_s"])

    @property
    def epsilon_m(self) -> float:
        """Direction dead-band eps, in metres.

        The manuscript requires eps to exceed the combined positional
        uncertainty of the two fixes that enter the difference
        d(t + dt) - d(t). Treating the two fixes as independent, the standard
        deviation of that difference is sqrt(2) * sigma_h, so

            eps = k * sqrt(2) * sigma_h

        with k the coverage multiplier (``epsilon_sigma_multiplier``). An
        explicit ``epsilon_m`` in the configuration overrides the derivation but
        is still checked against the same floor.
        """
        kin = self.raw["kinematics"]
        sigma_h = float(kin["groundtruth_sigma_h_m"])
        k = float(kin["epsilon_sigma_multiplier"])
        derived = k * math.sqrt(2.0) * sigma_h
        explicit = kin.get("epsilon_m")
        if explicit is None:
            return derived
        if float(explicit) < derived:
            raise ConfigError(
                f"epsilon_m={explicit} m is below the uncertainty floor "
                f"{derived:.3f} m implied by sigma_h={sigma_h} m and k={k}"
            )
        return float(explicit)

    @property
    def epsilon_floor_m(self) -> float:
        kin = self.raw["kinematics"]
        return float(kin["epsilon_sigma_multiplier"]) * math.sqrt(2.0) * float(
            kin["groundtruth_sigma_h_m"]
        )

    def clock_sigma_s(self, source_class: str) -> float:
        """1-sigma clock-offset uncertainty for a source class, in seconds."""
        table = self.raw["synchronization"]["clock_uncertainty_ms"]
        if source_class not in table:
            raise ConfigError(f"unknown source class {source_class!r}")
        return float(table[source_class]) / 1000.0

    def half_width_s(self, source_class: str) -> float:
        """Half-width of the uncertainty-expanded interval, in seconds."""
        k = float(self.raw["synchronization"]["uncertainty_expansion_k"])
        return k * self.clock_sigma_s(source_class)

    def allowed(self, vocab_name: str) -> List[str]:
        try:
            return list(self.vocab[vocab_name])
        except KeyError as exc:  # pragma: no cover - configuration error
            raise ConfigError(f"no controlled vocabulary named {vocab_name!r}") from exc


def _check(cfg: Dict[str, Any]) -> None:
    """Fail fast on configurations that would silently produce wrong numbers."""
    splits = cfg["splits"]
    total = splits["train"] + splits["val"] + splits["test"]
    if abs(total - 1.0) > 1e-9:
        raise ConfigError(f"split fractions sum to {total}, expected 1.0")

    poly = cfg["zone"]["polygon_en_m"]
    if len(poly) < 3:
        raise ConfigError("warning-zone polygon needs at least three vertices")

    win = cfg["windows"]
    if win["window_hop_s"] > win["window_span_s"]:
        raise ConfigError("window_hop_s exceeds window_span_s; windows would have gaps")

    sync = cfg["synchronization"]
    if sync["min_overlap_s"] <= 0:
        raise ConfigError("min_overlap_s must be positive")

    ft = cfg["field_trial"]
    if not 0.0 < ft["null_detection_rate"] < ft["target_detection_rate"] < 1.0:
        raise ConfigError(
            "field_trial rates must satisfy 0 < null_detection_rate "
            "< target_detection_rate < 1"
        )


def load(config_path: Path | str | None = None,
         vocab_path: Path | str | None = None) -> Config:
    """Load and validate the pipeline configuration."""
    cpath = Path(config_path) if config_path else DEFAULT_CONFIG
    vpath = Path(vocab_path) if vocab_path else DEFAULT_VOCAB
    cfg = yaml.safe_load(cpath.read_text(encoding="utf-8"))
    vocab = yaml.safe_load(vpath.read_text(encoding="utf-8"))
    _check(cfg)
    obj = Config(raw=cfg, vocab=vocab, source_path=cpath)
    obj.epsilon_m  # trigger the eps floor check at load time
    return obj
