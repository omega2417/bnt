# Zenodo deposit — UMSF Cyber-Range Digital Twin (SIM reproducibility package v2.0.0)

This directory holds the prepared Zenodo deposit and the ZIP built from it.

| Path | Contents |
|---|---|
| `umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0/` | The deposit tree (source of truth) |
| `umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0.zip` | The archive to upload to Zenodo, rebuilt by `scripts/build_package.sh` |

Start with the deposit's own `README.md`, then `zenodo/upload_checklist.md`.

Rebuild the whole campaign and the archive from scratch:

```sh
cd umsf-cyberrange-digital-twin-sim-reproducibility-package-v2.0.0
make clean && make all      # 40/40 checks, 86/86 reference values
./scripts/build_package.sh  # regenerates manifests, checksums and the ZIP
```

The evidence boundary of the deposit applies to everything here: all numerical
results are synthetic outputs of a software model in SIM mode, not measurements
of the physical cyber range.
