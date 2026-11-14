"""Remove generated caches only; preserve reports and original results."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
for folder in ('satqkd_sentinel','scripts','tests'):
    shutil.rmtree(root/folder/'__pycache__',ignore_errors=True)
shutil.rmtree(root/'.pytest_cache',ignore_errors=True)
