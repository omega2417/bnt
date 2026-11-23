from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def released():
    """The pre-generated results shipped with the package."""
    path = ROOT / "results"
    if not (path / "logs" / "C0" / "trace_summary.csv").exists():
        pytest.skip("released results not present")
    return path
