# Meshtastic Logistics Metadata Collector

Software accompanying the manuscript *Strengthening Economic Autonomy in Small and Medium-Sized Enterprise
Logistics with Meshtastic Mesh Networks: Visual Analytics and Investment Appraisal*.

It collects radio, device and logistics-event metadata from a private Meshtastic LoRa mesh network on a local
gateway (no Internet needed) and computes the indicators used in the article, so that a field pilot can replace
the model assumptions with measured values.

> **Status.** Prototype verified on **synthetic data only** (no radio hardware, no field measurements).
> Tested with `meshtastic` 2.7.11 and Python 3.11–3.13.

## Contents

| File | Purpose |
|---|---|
| `logi_proto.py` | 24-byte binary frame for EVENT / ACCEPT / DONE / REJECT / HEARTBEAT on PRIVATE_APP (port 256), CRC-16/CCITT |
| `collector.py` | gateway collector: L1 packet, L2 device and L3 logistics-event metadata → SQLite; serial, TCP or offline replay |
| `schema.sql` | metadata store schema (L1–L4), SQLite ≥ 3.35, portable to PostgreSQL/TimescaleDB |
| `kpi.py` | KPIs: channel utilization *U*, flood overhead, position delivery ratio *p*, age of information, actionability *η* (Eq. 9), operational autonomy *A*ₒₚ, loss reduction *R*ₗₒₛₛ |
| `import_plan.py` | imports planned critical operations (denominator of *A*ₒₚ) |
| `make_replay.py` | synthetic replay log: 3 vehicles, 6 h, ~15 % lost positions, flood copies, relay telemetry, 4 critical events |
| `run_demo.sh` | one-command reproduction on synthetic data |
| `tests/` | unit and end-to-end tests (standard library `unittest`) |
| `examples/expected_kpi_synthetic.json` | reference KPI output of the synthetic run |
| `docs/software_proposal_uk.md` | full design document (in Ukrainian): metadata levels, architecture, protocol, data-quality and privacy rules, rollout plan |

## Requirements

- Python 3.11+ (replay mode, KPIs and tests use the standard library only).
- Live radio mode: `pip install -r requirements.txt` (`meshtastic`, `pypubsub`) and a Meshtastic node on USB or TCP.

## Reproduce the synthetic results

```sh
./run_demo.sh            # or step by step:
python3 make_replay.py
python3 collector.py --replay packets.jsonl --db test.db
python3 import_plan.py --db test.db --plan ops.json --loss 1000
python3 kpi.py --db test.db --from 1800000000 --to 1800021600
```

The output must equal `examples/expected_kpi_synthetic.json`
(`flood_overhead` 0.267, `eta_actionability` 0.5, `A_op` 0.5, `R_loss` 0.5, …). Run the tests with

```sh
python3 -m unittest discover -s tests -v
```

They check that flood duplicates are separated from delivery, that events move RECEIVED → ACCEPTED → DONE,
that completion after the deadline is not counted in *η* and *A*ₒₚ, that corrupted frames are rejected by CRC,
and that every event reaches `sync_outbox`.

## Live use on a gateway

```sh
python3 collector.py --serial /dev/ttyUSB0 --db logi.db
python3 collector.py --tcp 192.168.1.50 --db logi.db
python3 kpi.py --db logi.db --from <unix_start> --to <unix_end>
```

Business messages should use a separate private channel with its own key. Vehicle positions linked to a driver
are personal data: keep `asset_ref` pseudonymised and limit retention (see `docs/software_proposal_uk.md`, §9).

## Citation

See `CITATION.cff`. After the Zenodo deposit, cite the version DOI shown on the record.

## License

MIT, see `LICENSE`.
