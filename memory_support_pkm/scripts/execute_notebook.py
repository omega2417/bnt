"""Execute a notebook in a temporary directory and store its outputs in place."""
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

path = Path(sys.argv[1]).resolve()
nb = nbformat.read(path, as_version=4)
with tempfile.TemporaryDirectory() as tmp:
    NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": tmp}}).execute()
errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.output_type == "error"]
if errors:
    sys.exit(f"{len(errors)} cell(s) failed")
nbformat.write(nb, path)
print("executed:", path)
