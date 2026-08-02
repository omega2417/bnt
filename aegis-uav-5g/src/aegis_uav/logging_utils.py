"""Structured logging helpers.

Emits JSON-lines to a run log file and human-readable lines to stderr so runs
are both greppable and auditable.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

__all__ = ["get_logger", "configure_logging"]

_CONFIGURED = False


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_logging(log_file: Path | None = None, level: int = logging.INFO) -> None:
    """Configure the root ``aegis_uav`` logger once."""
    global _CONFIGURED
    root = logging.getLogger("aegis_uav")
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
    root.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(_JsonLineFormatter())
        root.addHandler(fh)

    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(f"aegis_uav.{name}")


def log_event(logger: logging.Logger, message: str, **fields) -> None:
    """Log ``message`` with structured ``fields`` attached to the JSON record."""
    logger.info(message, extra={"extra_fields": fields})
