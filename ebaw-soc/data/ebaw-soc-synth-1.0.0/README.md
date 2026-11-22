# EBAW-SOC-Synth 1.0.0

Synthetic agentic response episodes with evidence-bound action warrants: 900 episodes, 6300 proposals
(615 adversarial), nine linked CSV tables. See `DATASHEET.md` for composition and intended use and
`datapackage.json` for the field dictionary. License: CC BY 4.0 (`LICENSE`).

```python
from ebaw import dataset          # ebaw-soc 2.0.0
D = dataset.load("data/ebaw-soc-synth-1.0.0")
dataset.validate("data/ebaw-soc-synth-1.0.0")   # digests, signatures, schema, volumes, invariants
```

Without the package: `pandas.read_csv("proposals.csv")`. Join tables on `proposal_id`, `episode_id` or `evidence_id`.
