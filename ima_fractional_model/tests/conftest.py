import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from src import load_graph


@pytest.fixture(scope="session")
def graph():
    return load_graph(ROOT / "config" / "ima_22node.yaml")
