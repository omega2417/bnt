# dt_power_hil — software–hardware experiment for the digital twin of a communication-node power supply

Implementation of the protocol “Software–hardware experiment for the digital twin of a communication-node power supply” (v1.0) for the manuscript
*Digital Twin of Power Supply for a Communication Node During Outages* (Applied Energy).

**Evidence class of everything in `results/`:** SIL with emulated hardware (virtual testbed). There are no physical measurements.

| Part | Location |
|---|---|
| Software: twin, EMS, virtual testbed, analysis | `dtpower/`, `scripts/`, `tests/`, `configs/` |
| ESP32-S3 firmware (ESP-IDF, not compiled) | `firmware/esp32_edge_guard/` |
| Hardware: BOM on real components, diagram, installation | `hardware/BOM_and_wiring.md` |
| Measurement protocols P-1…P-7 | `hardware/measurement_protocols.md`, `results/protocols/` |
| Elsevier-style report (English) | `report/DT_HIL_Experiment_Report_Elsevier_EN.docx` |
| Web dashboard (English) | `web/index.html` |
| Ukrainian versions | `*_UA.*` files, `scripts/*_ua.py`, `web/template_ua.html` |

## Reproduction

```bash
pip install numpy scipy matplotlib python-docx pytest
python -m pytest -q tests                 # software acceptance checks (protocol §18.3)
python scripts/run_campaign.py            # E00–E11 → results/ (≈ 80 s on 4 cores)
python scripts/make_figures.py            # results/figures/*.png|pdf
python scripts/make_protocols.py          # hardware/measurement_protocols.md
python scripts/make_report.py             # report/DT_HIL_Experiment_Report_Elsevier_EN.docx
python scripts/make_web.py                # web/index.html (+ web/index_UA.html)
```

## Moving to the physical bench

1. Fill in the bench passport and P-1 with the actual datasheets/nameplates; replace the calibration-standard placeholders in `configs/hardware_bench_12v.json`.
2. In `dtpower/bench.py`, replace the emulated `BatteryPlant` / `PowerMonitorChannel` / `Channel` with drivers for the RD6018 (Modbus), the INA228 logger and an MQTT client; the `twin`, `ems` and `stats` logic stays unchanged.
3. Build and flash `firmware/esp32_edge_guard`, then repeat the E10 vectors on the target.
4. E00 → pilot E01–E05 → freeze thresholds → main C0/C1/C2 series (≥ 3 repeats) with `mode = "physical"`.
