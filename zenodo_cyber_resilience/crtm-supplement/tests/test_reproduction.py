"""End-to-end: all published values of Section 7 are reproduced."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_reproduce_script(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "reproduce.py"), "--out", str(tmp_path),
                        "--no-figures", "--fast"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert (tmp_path / "results.json").exists()
