"""The dependency-free script is an independent second implementation of the formulas."""
import ast
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "supplementary" / "worked_example.py"


def test_script_passes():
    run = subprocess.run([sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True)
    assert run.returncode == 0 and "all values agree with the manuscript" in run.stdout
    assert "MISMATCH" not in run.stdout


def test_script_uses_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert mods == {"fractions", "itertools"}
