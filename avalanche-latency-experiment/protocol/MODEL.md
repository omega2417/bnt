# The reference model, and what it is not

`alp.simulate` produces a dataset in the campaign's exact schema without a
cyber range. It exists so that every downstream stage — metric derivation,
the statistical plan, the stability rules, the tables, the figures and the
report — can be executed, reviewed and tested before the real campaign
runs, and so that a reviewer can re-execute the whole pipeline in a
notebook.

**It is not a measurement.** Every record it writes carries
`provenance = "SIMULATED"`, every table and figure prints that label, and
the generated report opens with a banner saying so. Numbers produced from
it must never appear in a Results section as experimental findings.

## What the model represents

The measured path of protocol section 6, stage by stage:

1. **Ingress.** The client's RPC leg plus gossip to the proposer, with
   multiplicative lognormal jitter whose sigma is a property of the topology.
2. **Block production.** Blocks are produced on the cadence `B` of the
   profile. A block admits `min(backlog, gas_limit / gas_per_tx)`
   transactions. When the previous block's execution cost exceeds `B`, the
   next proposal slips, so the observed interval inflates under load.
3. **Consensus acceptance.** A per-block delay: a jittered base plus a
   Bernoulli "slow round" penalty. The penalty is drawn **per block**, so
   latency is correlated inside a block exactly as on a real chain — which
   is why the statistical plan treats the run, not the transaction, as the
   inferential unit.
4. **Execution and commit.** Storage latency inflates once the per-block
   work approaches the block period.
5. **Read visibility.** Each read node applies the accepted block after an
   independent delay; the second node is further away than the first, so
   convergence is not instantaneous.
6. **Client discovery.** Receipts and reads are discovered on the 25 ms
   polling grid, reproducing the discretisation error of protocol 15.2.

## Where the interesting behaviour comes from

* **Capacity.** `gas_limit / gas_per_tx` transactions per block over the
  block period is the gas-limited ceiling. It is what makes the slow
  profiles saturate at high load while the fast ones do not.
* **CPU pressure.** `cpu = (a * blocks/s + b * tx/s) / (1000 * cores)`. The
  block term does not vanish at low load: halving the interval doubles the
  consensus work whether or not any transaction arrives. This is the
  mechanism behind RQ2.
* **Degradation under pressure.** The slow-round probability is scaled by
  `1 + gain * max(0, pressure - knee) ** exponent`. This is the mechanism by
  which the profile with the best median need not own the tail (H3).

## Parameters and their real-campaign replacements

All parameters are in `alp.model`, are serialised into every run passport,
and are echoed by `python -m alp info --model`. Each carries the
DATA REQUIRED field that supersedes it: `gas_limit` comes from genesis,
`t_exec_ms` and the CPU coefficients from node telemetry, the topology
delays from the measured RTT matrix, and `STOCK_BLOCK_MS` from the observed
interval of the deployed stock configuration.

## Known limitations of the model

* Validators are homogeneous; a real set is not.
* Byzantine behaviour, node restarts, VPN route failover and power events
  are not modelled — they are abort criteria in the protocol, not regimes.
* Gas price dynamics and mempool eviction policy are not modelled: the
  probe transaction has a fixed cost and the mempool is unbounded.
* The read path assumes a read node applies a block as a whole; partial
  state exposure is not represented.
* Wi-Fi and access-point behaviour, which the cyber range can exercise, is
  outside the model entirely.

A campaign that contradicts the model is not a failure of the campaign. The
model's only job is to keep the analysis honest and executable until real
logs exist.
