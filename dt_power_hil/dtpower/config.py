"""Configuration loading, validation and hashing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "configs"

VALID_MODES = ("physical", "chil_realtime", "controller_replay", "sil", "sil_hw_emulated")


def load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def config_hash(cfg: dict) -> str:
    return sha256_bytes(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8"))


class ConfigError(ValueError):
    pass


def validate_run_config(run: dict) -> None:
    """Reject a run the way section 21.4 of the protocol demands."""
    mode = run.get("mode")
    if mode not in VALID_MODES:
        raise ConfigError(f"unknown mode {mode!r}")
    if mode == "physical" and run.get("acceleration", 1) != 1:
        raise ConfigError("acceleration must be 1 in physical mode")
    ctrl = run.get("control", {})
    off, on = ctrl.get("aux_off_soc"), ctrl.get("aux_on_soc")
    if off is not None and on is not None and not off < on:
        raise ConfigError("aux_off_soc must be below aux_on_soc (hysteresis)")
    stop = run.get("stop_soc_reference")
    if stop is not None and off is not None and not stop < off:
        raise ConfigError("stop threshold must be below aux_off_soc")
    if mode == "physical":
        required = ["nameplate_voltage_v", "nameplate_capacity_ah", "measured_capacity_ah"]
        missing = [k for k in required if run.get("battery", {}).get(k) is None]
        if missing:
            raise ConfigError(f"physical run blocked: missing battery fields {missing}")
        if not run.get("independent_protection", False):
            raise ConfigError("physical run blocked: independent protection not confirmed")
