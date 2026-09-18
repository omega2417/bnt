"""Shared pytest configuration."""

from __future__ import annotations

import matplotlib


def pytest_configure(config):
    matplotlib.use("Agg")
    config.addinivalue_line("markers", "slow: runs a full search or figure pipeline")
