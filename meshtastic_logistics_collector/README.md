# Meshtastic Logistics Metadata Collector

Version 1.1.0 (28 November 2026). Software accompanying the manuscript *Strengthening Operational Autonomy in
Small and Medium-Sized Enterprise Logistics with Meshtastic Mesh Networks: Reference Architecture and Ex-Ante
Model-Based Assessment* (MDPI *Logistics*, manuscript logistics-4699826), where it is reference [54].

## What this is, and what it is not

> **Evidence status. No experiment has been performed with this software.**
>
> * It has **never been connected to a Meshtastic radio**. The `--serial` and `--tcp` code paths were written
>   from the documented API of `meshtastic` 2.7.11 and have not been executed against hardware.
> * It has been run **only on an invented replay log** produced by `make_replay.py`. In that log every
>   "radio" value is either pseudo-random or a constant typed in by hand, and the outcome of every
>   logistics event is scripted.
> * Consequently **no number produced by this package is a measurement**, and none of them confirms,
>   supports or validates any value in the article. The article's numbers are model predictions; they were
>   not produced by this software either (they come from separate scripts, `model.py` and `figures.py`).
> * The package is a *measurement instrument that still has to be tried*: it defines what a field
>   experiment would record and how the indicators would be computed, so that these rules are fixed before
>   any measurement is made.

The software enforces this distinction itself: every ingest run is registered with its data origin, and
`kpi.py` starts its output with a `provenance` block. For anything other than radio data the block says
`"is_measurement": false` and `NOT A MEASUREMENT`.

## Contents

| File | Purpose |
|---|---|
| `logi_proto.py` | 24-byte binary frame for EVENT / ACCEPT / DONE / REJECT / HEARTBEAT on PRIVATE_APP (port 256), CRC-16/CCITT |
| `collector.py` | gateway collector: packet (L1), device (L2) and logistics-event (L3) metadata → SQLite; serial, TCP or offline replay; records the data origin of every run |
| `schema.sql` | metadata store schema (L1–L4 and `collector_session`), SQLite ≥ 3.35 |
| `kpi.py` | indicators with provenance, sample sizes and 95 % intervals (definitions below) |
| `import_plan.py` | imports the list of planned critical operations (denominator of *A*ₒₚ) |
| `make_replay.py` | generator of the invented replay log (test input, not data) |
| `run_demo.sh` | one-command software check on the generated input |
| `tests/` | unit and end-to-end tests (standard library `unittest`), including the accounting rules |
| `examples/expected_kpi_synthetic.json` | reference output of the software check |
| `notebooks/meshtastic_logistics_analysis.ipynb` | walk-through of the calculations on the generated input; recomputes printed values of the article from its printed equations and checks the algebra of Equation (3) |
| `docs/software_proposal_uk.md` | design document (in Ukrainian) |

## Indicators and their relation to the article

| Output key | Definition | Article |
|---|---|---|
| `channel_util_max_pct`, `relay_airtime_max_pct` | largest `channelUtilization` / `airUtilTx` **reported by a node** in its telemetry; the collector does not compute them | *U*, relay airtime (Table 9, row 1) |
| `flood_overhead` | duplicate copies per unique packet as seen through the gateway API | not used in the article |
| `position_delivery_ratio` | positions received / positions expected for the configured interval (not clipped at 1) | *p* (Table 9, row 3) |
| `aoi_mean_min`, `aoi_max_min` | time-average and maximum age of the last received position, from the first reception to the end of the window (the silent tail is included) | AoI, Equation (3) |
| `eta_actionability` | critical events completed before their deadline / critical events delivered to the gateway | measurement rule for *η* in Table 9 |
| `A_op` | planned critical operations completed by their due time / all planned critical operations | *A*ₒₚ (Table 9, row 5) |
| `on_time_share_loss_weighted` | the same share weighted by the assumed loss of each operation | loss-weighted *A*ₒₚ, Equation (5) |

Three points must be read with care.

1. `eta_actionability` follows the measurement rule of Table 9. It is an **upper bound** of the efficacy *η*
   of Equation (4): completing an operation on time does not prove that the loss was avoided. Whether it
   was requires the baseline loss records of the field experiment, which this software does not collect.
2. `on_time_share_loss_weighted` is an upper bound of the avoided-loss share *q* (reached only if *η* = 1).
   Version 1.0.0 called this value `R_loss` ("loss reduction"). That name claimed more than the quantity
   measures and has been removed.
3. Deadlines run from the creation of an event on the sender, so radio latency is counted against them.
   Only if the sender clock is unset does the deadline start at gateway reception; `kpi.py` then warns.

All ratios come with numerator and denominator (`*_n`) and a 95 % Wilson interval (`*_ci95`).

## What the collector records of the planned field experiment (Table 9 of the article)

| Quantity in Table 9 | Recorded? | Remark |
|---|---|---|
| Channel utilisation *U*, relay airtime | yes, if the nodes send device telemetry | values are those reported by the firmware |
| Operational autonomy *A*ₒₚ | yes, against a plan imported beforehand | |
| Efficacy *η* (Table 9 rule) | yes, as an upper bound | see point 1 above |
| Delivery of critical events | partly | the gateway knows only the events that reached it; the number *sent* needs a log on the vehicle |
| Position delivery and AoI | partly | received positions are stored; the on-board GNSS reference track is external |
| Vehicle range and route coverage | partly | position, SNR, RSSI and hop count are stored; no coverage map is computed |
| Level of manual procedures *m* | no | needs manual records of operations outside mesh coverage |
| Level of second-operator backup | no | needs a separate scenario and records |
| Dispatch side on backup power | no | outage windows can be entered in the table `outage` by hand; nothing detects them |

So the collector covers three of the nine quantities completely and three partly.

## Known limitations

* **Not tested on hardware** (see above). Field names, units and the behaviour of `sendData` must be checked
  against the firmware version actually used.
* **Flood duplicates may be invisible on a real gateway.** Meshtastic firmware discards packets it has
  already seen before they reach the client API, so `rx_duplicates` and `flood_overhead` may be zero on
  real hardware whatever the amount of rebroadcasting. The duplicate logic has only been exercised with
  duplicates written into the generated log. This must be verified before the field experiment.
* The **dispatcher dashboard** described in the article's architecture is **not part of this package**.
* `sync_outbox` only **queues** records for later synchronisation; no sender to an ERP/TMS is implemented.
* `outage` is filled by hand; the collector does not detect connectivity or power failures.
* A gateway sees only what reaches it. Losses on the way are inferred from the configured position
  interval, not observed.
* The generated log has 3 vehicles and 4 scripted events. With 2 of 4 operations on time the 95 % interval
  of *A*ₒₚ is 0.15–0.85, which the output states explicitly.

## Requirements

- Python 3.11+ (replay mode, indicators and tests use the standard library only; checked with Python 3.13).
- Live radio mode (untested): `pip install -r requirements.txt` (`meshtastic`, `pypubsub`) and a Meshtastic
  node on USB or TCP.

## Run the software check

```sh
./run_demo.sh            # or step by step:
python3 make_replay.py
python3 collector.py --replay packets.jsonl --db test.db
python3 import_plan.py --db test.db --plan ops.json --loss 1000
python3 kpi.py --db test.db --from 1800000000 --to 1800021600
```

The output must equal `examples/expected_kpi_synthetic.json`. A match shows that the code is deterministic.
It does not validate the numbers, which are properties of `make_replay.py`: for example
`channel_util_max_pct` = 4.2 is a constant written into the generator near the article's predicted 3.92 %,
and `A_op` = 0.5 follows from the script that lets two of four events finish on time.

```sh
python3 -m unittest discover -s tests -v
```

The tests check the frame codec and CRC, the separation of duplicates from delivery, the event life cycle,
that late completion and radio latency are not counted as success, that operations without any message stay
in the denominator, that an empty plan gives an undefined (not zero) *A*ₒₚ, that a replay file cannot
declare itself live radio data, and that generated or unlabelled input is never reported as a measurement.

## Analysis notebook

Open `notebooks/meshtastic_logistics_analysis.ipynb` in Jupyter, or upload it together with the package to
Google Colab. It needs `pandas`, `numpy` and `matplotlib`. The notebook is saved with its outputs. It
contains checks that do not depend on the generated log. The equations printed in the article are
evaluated on its printed assumptions and reproduce its printed values (airtime and range of Table A2,
channel utilisation 3.92 %, break-even share 0.354, efficacy threshold 0.612, payback 17.1 months, NPV
718 EUR), and a Monte Carlo simulation reproduces Equation (3) under the equation's own assumption of
independent losses. These are checks of arithmetic, not of the assumptions.

## Use on a gateway (untested)

```sh
python3 collector.py --serial /dev/ttyUSB0 --db logi.db
python3 collector.py --tcp 192.168.1.50 --db logi.db
python3 kpi.py --db logi.db --from <unix_start> --to <unix_end> --position-interval 600
```

Business messages should use a separate private channel with its own key. Vehicle positions linked to a
driver are personal data: keep `asset_ref` pseudonymised and limit retention
(see `docs/software_proposal_uk.md`, §9). Do not mix generated and radio data in one database; if this
happens, `kpi.py` reports the origin as `mixed` and not as a measurement.

## Versions and citation

Version 1.0.0 is archived at https://doi.org/10.5281/zenodo.23796017. Version 1.1.0 changes the definitions
and names of several indicators (see `CHANGELOG.md`), so results of the two versions are not comparable.
It is to be deposited as a new version of the same Zenodo record; its version DOI is assigned by Zenodo at
deposit and is deliberately not stated here. See `CITATION.cff`.

Generative AI (Claude, Anthropic) assisted in writing this software, as disclosed in the article. The
author reviewed it and is responsible for its content.

## License

MIT, see `LICENSE`.
