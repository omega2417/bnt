# Changelog

## 1.0.0 — 2026-10-30
First archived release (Zenodo).
- `logi_proto.py`: 24-byte EVENT/ACCEPT/DONE/REJECT/HEARTBEAT frame with CRC-16/CCITT.
- `collector.py`: L1–L3 metadata collector (serial, TCP, offline replay) with flood de-duplication and sync outbox.
- `schema.sql`: SQLite metadata store (L1–L4).
- `kpi.py`: U, flood overhead, position delivery ratio, AoI, η, A_op, R_loss.
- `make_replay.py`: synthetic replay log; event ids are now deterministic (fixed seed), so runs are bit-reproducible.
- `import_plan.py`, `run_demo.sh`: import of planned operations and one-command reproduction.
- `tests/`: unit and end-to-end tests against `examples/expected_kpi_synthetic.json`.
