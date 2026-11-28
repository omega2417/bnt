# Changelog

## 1.1.0 — 2026-11-28
Revision made in response to peer review of the accompanying manuscript (logistics-4699826, Reviewer 3).
Its purpose is that no output of this package can be mistaken for a measurement. No new functionality for
radio hardware was added, and the software has still not been run on a radio.

Evidence status and provenance
- New table `collector_session`: every ingest run declares its data origin (`synthetic`, `recorded_live`,
  `live_radio`, `unlabelled`). A replay file cannot declare itself `live_radio`.
- `kpi.py` output starts with a `provenance` block; for generated, unlabelled or mixed input it states
  `"is_measurement": false` and "NOT A MEASUREMENT".
- `make_replay.py` writes a meta line that marks the log as synthetic, and documents which values are
  pseudo-random and which are hand-set constants (including channel utilisation 4.2 % and relay airtime
  1.3 %, which were chosen near the article's predictions and therefore confirm nothing).

Indicators (results are not comparable with 1.0.0)
- `R_loss` renamed to `on_time_share_loss_weighted`. It is a loss-weighted share of operations completed on
  time and an upper bound of the avoided-loss share *q*; it never was a measured loss reduction.
- `eta_actionability` is documented as the measurement rule of Table 9 and an upper bound of *η* in
  Equation (4); it now counts critical events (priority 3) only.
- Ratios are reported with numerator/denominator and a 95 % Wilson interval; small samples raise a warning.
- Deadlines start at event creation (sender clock), so radio latency counts against them; 1.0.0 started
  them at gateway reception, which excused any radio delay.
- Age of information includes the silent tail after the last reception; `aoi_max_min` is new and
  `stale_nodes` now lists nodes that were stale at any time in the window (1.0.0 looked only at its end).
- `position_delivery_ratio` is no longer clipped at 1; the position interval is a parameter.
- SNR and hop averages use unique packets only.
- Loss column renamed from `loss_if_failed_uah` to currency-neutral `loss_if_failed` (the article uses EUR).

Corrections
- References to "Equation (9)" corrected to Equation (4) / Table 9 of the revised manuscript; manuscript
  title updated; economic figures quoted in the notebook corrected to the article's values in EUR.
- A late or repeated ACCEPT no longer moves a finished event back to `ACCEPTED`; the first DONE/REJECT wins.
- Replies to events the gateway never received are logged and not counted.
- `make_replay.py`: ACCEPT/DONE frames took their timestamp from the wall clock, so the 1.0.0 output was
  not bit-reproducible although its changelog said so. Fixed; a test now checks it.
- The notebook no longer compares synthetic values with the article's thresholds and no longer states that
  synthetic output "matches the article".
- Placeholder authors replaced by the author named in the article's reference [54].

Documentation
- README states what was and was not tested, what the collector records of Table 9 (three of nine
  quantities completely, three partly), and known limitations (no hardware test, possible invisibility of
  flood duplicates on real firmware, no dashboard, no synchronisation sender, manual outage log).

## 1.0.0 — 2026-10-30
First archived release (Zenodo, https://doi.org/10.5281/zenodo.23796017).
- `logi_proto.py`, `collector.py`, `schema.sql`, `kpi.py`, `make_replay.py`, `import_plan.py`, `run_demo.sh`,
  notebook and tests. Verified on generated data only.
