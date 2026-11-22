"""Build and validate the EBAW-SOC-Synth dataset (data/ebaw-soc-synth-1.0.0/)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ebaw import dataset  # noqa: E402

OUT = os.path.join(ROOT, "data", f"ebaw-soc-synth-{dataset.DATASET_VERSION}")

if __name__ == "__main__":
    dataset.build(OUT)
    sys.exit(1 if dataset.validate(OUT) else 0)
