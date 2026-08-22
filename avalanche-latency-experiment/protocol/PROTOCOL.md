# Experimental protocol

Reproducible field experiment on the latency of access to confirmed state
in a permissioned Avalanche L1 (Subnet-EVM), conducted on the two-site
cyber range of the University of Customs and Finance.

This file is the executable specification. Every constant it states lives
in `src/alp/config.py`, so the protocol and the code cannot drift apart.
Section numbers follow the source protocol document.

---

## 1. Value classes

| Class | Meaning | Example |
| --- | --- | --- |
| `CONFIRMED` | stated in the laboratory description | 25 Kali Linux workstations |
| `PROTOCOL` | chosen in advance for the reproducible campaign | 300 s measurement window |
| `DERIVED` | arithmetic consequence of the above | 750 runs |
| `THEORY` | closed-form result under stated assumptions | `Q_p(W_block) = pB` |
| `MODEL` | reference-simulator parameter | per-block CPU cost |
| `DATA REQUIRED` | obtainable only from a real campaign | measured p50/p95/p99 |

A number never changes class silently. Theoretical values are never copied
into the result tables, and the reference model is never reported as a
measurement.

### 1.1 Known source conflict

The laboratory description confirms **two** physical sites; the study design
calls for local, single-region and three-region topologies. No third site,
remote host or cloud node is documented anywhere in the sources. The
protocol therefore realises `T2` as an **emulated** three-region topology
using `tc netem`, and labels it as such in every table and figure. If a
third physical site is used in the real campaign, replace the emulation and
re-label.

---

## 2. Confirmed experimental base

| Item | Site A (main building) | Site B (branch) |
| --- | --- | --- |
| Edge router | Keenetic Titan | Keenetic Viva |
| WAN | 3 x 1 Gbit/s + 2 x 100 Mbit/s | 2 x 1 Gbit/s |
| Wi-Fi controller | UniFi CloudKey Gen2 | UniFi CloudKey Gen1 |
| Access points | 48 (12 with gigabit uplink) | 6 (100 Mbit/s uplink) |
| Other | 3 x EcoFlow power backup | 25 Kali Linux workstations |

Nominal link speeds are sums of interface ratings. They are not
single-session throughput: Multi-WAN policy, protocol overhead, the VPN,
switch bottlenecks and per-session limits all intervene. The CloudKey is a
management plane, not a transit node of the transaction path.

### 2.1 Mapping onto the experiment

Five validators and two independent read nodes: `V1`-`V3` and `R1` on site
A, `V4`-`V5` and `R2` on site B. This placement is a reproducible protocol
decision, not an audited inventory. Each of the 25 generators owns one EVM
account, which removes nonce conflicts between workstations.

---

## 3. Aim, questions, hypotheses

**Aim.** Determine the conditions under which a shorter minimum block
interval reduces user-visible latency without unstable queue growth,
execution overload or loss of state consistency.

* **RQ1** How do the 1000 / 750 / 500 / 250 ms profiles change p50, p95 and
  p99 of `T_visible` against the stock configuration of the same version?
* **RQ2** At which offered load does a shorter interval stop paying off,
  because of queue growth, CPU, disk I/O or read latency?
* **RQ3** Does the effect survive in local, two-site VPN and emulated
  three-region topologies?
* **RQ4** Which configuration is the best static one, subject to acceptable
  availability and state consistency?

**Pre-registered hypotheses.** `H1` shorter pacing lowers the block-wait
component. `H2` the realised gain is non-linear and shrinks as network and
execution queues grow. `H3` the 250 ms profile may have the lowest median at
low load without owning the p99 or the largest sustainable load.

The decision rule for each hypothesis is stated in
`alp.report.hypothesis_verdicts` and is evaluated by code, not by reading
the tables.

---

## 4. Factorial design

| Factor | Levels | Count |
| --- | --- | --- |
| Configuration `C` | C0 stock; C1 1000; C2 750; C3 500; C4 250 ms | 5 |
| Topology `T` | T0 local; T1 physical VPN; T2 emulated three-region | 3 |
| Load `lambda` | 25; 50; 100; 200; 400 tx/s | 5 |
| Repeat `r` | 1...10 | 10 |

```
N_runs   = 5 * 3 * 5 * 10                       = 750            (1)
t_run    = 60 s + 300 s + 60 s                  = 420 s          (2)
T_wall   = 750 * 420 s = 315 000 s              = 87.50 h        (3)
N_TX     = 300 * 775 * 5 * 3 * 10               = 34 875 000     (4)
```

Failed or rejected transactions are **not** removed from the denominator.

### 4.1 Topologies

| Code | Realisation | Recorded |
| --- | --- | --- |
| `T0_local` | all nodes on one isolated LAN, no netem | actual RTT/jitter/loss |
| `T1_vpn` | validators split across sites, traffic over the VPN | VPN protocol, MTU, routes, RTT/jitter/loss |
| `T2_three_region_emulated` | 2+2+1 placement, netem targets 20/50/80 ms, jitter 2 ms, loss 0.1 % | targets *and* the realised matrix before and after netem |

### 4.2 Randomisation and paired traces

For every `load x repeat` pair the campaign pre-computes one arrival trace
with a fixed derived seed (`alp.traces`). Every configuration and topology
replays the same trace, which makes the design paired. The order of
configurations is randomised inside each `topology x load` block
(`alp.schedule`) to break confounding with time of day, ambient traffic,
thermal drift and disk warm-up.

Clients replay pre-generated timestamps. They never draw new random
intervals during a run.

---

## 5. Avalanche L1 configuration

Chain configs for the five profiles are in `deploy/chain-configs/`. For
Granite-compatible builds, ACP-226 introduces millisecond granularity and
the `min-delay-target` parameter; when ProposerVM is in play its
`proposerMinBlockDelay` is set to `0s` so it does not impose a second pacing
floor (`deploy/subnet-configs/subnet.json`).

`allow-unfinalized-queries` stays **false** on every read node: a read that
can return unfinalized state would not measure confirmed-state access.

**Version check is mandatory.** AvalancheGo and Subnet-EVM versions,
commits, the active network upgrade, chain/subnet/blockchain IDs, genesis
and the fee/gas configuration are DATA REQUIRED. Do not transplant the JSON
of `deploy/` onto a different version without checking its config schema.
Verify the effective pacing against real block headers after every restart.

---

## 6. Probe transaction and the definition of confirmed state

`contracts/VisibilityProbe.sol` stores a monotonic sequence number per key.
After a receipt with `status = 1`, the client polls `R1` and `R2` through
`eth_call` at `block_identifier = "latest"`. The write is visible on read
node `r` once the returned sequence is at least the submitted one. The
primary metric uses the **earliest** independent read; the convergence
metric uses the **latest**.

---

## 7. Metric model

```
T_visible,first(i) = min_r t_read(i,r) - t_send(i)                     (5)
T_visible,all(i)   = max_r t_read(i,r) - t_send(i)                     (6)
T_convergence(i)   = max_r t_read(i,r) - min_r t_read(i,r)             (7)
Q_p(T)             = inf{x : F_T(x) >= p},  p in {0.50, 0.95, 0.99}    (8)
G                  = N_success / dt_measure                     [tx/s] (9)
A                  = N_success / N_submitted * 100 %                  (10)
C                  = N_agree / N_success * 100 %                      (11)
dQ_p(%)            = (Q_baseline - Q_profile) / Q_baseline * 100 %     (12)
B_obs              = median_k(t_block,k - t_block,k-1)                (13)
s_Q                = TheilSenSlope(queue_depth, time)                 (14)
```

Every timestamp entering equations (5)-(7) is read from **one** monotonic
clock on the generator, so inter-host clock offset cannot enter the primary
metric. Each equation is transcribed in `src/alp/metrics.py` under the same
number.

---

## 8. Pre-experiment calculations

```
f_B                = 1000 / B_ms                        [blocks/s]    (15)
n_TX/block,req     = lambda * B_ms / 1000                             (16)
```

Under a uniform arrival phase, `W_block ~ U(0, B)` and `Q_p(W_block) = pB`.
These are the structural lower component of latency only: propagation,
acceptance, execution, commit and read are added separately and change the
shape of the distribution. **They are not `T_visible` and must never be
placed in a Results table.**

---

## 9. Procedure of one run

1. Isolate the blockchain segment; verify default-deny towards university
   production resources and uncontrolled external targets (`deploy/preflight.sh`).
2. Record the passport: date, time zone, `run_id`, git commit, SHA-256 of
   genesis / config / contract, NodeIDs, host inventory, active WAN/VPN route.
3. Apply profile `C` on every validator; for C1-C4 set `min-delay-target`.
   Restart nodes by the documented runbook.
4. Confirm that `V1`-`V5` are synchronised, that `R1`/`R2` see the same
   accepted head, that `allow-unfinalized-queries` is false, and that the
   effective block delay matches the profile.
5. For `T2` apply netem to isolated interfaces only and measure the realised
   RTT/jitter/loss matrix. For `T0`/`T1` apply no netem.
6. Check chrony/NTP and record the maximum offset.
7. Run the 60 s warm-up on the same trace; exclude those transactions from
   the analysis but not their effect on the queue.
8. Replay the 300 s measurement window, logging every transaction, receipt,
   `R1`/`R2` read, queue metric, CPU, memory, disk I/O and network probe.
9. Stop submitting; wait 60 s for receipts and timeouts without removing
   failures from the denominator.
10. Collect artefacts, build the SHA-256 manifest, check the transaction
    count against the expected one, clear netem, move to the next `run_id`.

### 9.1 Abort criteria

* a route is found from the test segment to a forbidden production or
  external resource;
* free disk on any node below 20 %;
* CPU at or above 95 % for 30 s together with a growing backlog or a lost
  health check;
* `R1`/`R2` disagree on the accepted head for more than 30 s;
* a validator crashes, the database reports corruption, or the VPN becomes
  unstable outside the planned scenario;
* the clock offset exceeds the pre-approved threshold.

A run aborted for any of these reasons is logged in the deviation record and
is not mixed into the main series.

---

## 10. Data layout

```
data/raw/tx/<run_id>.jsonl[.gz]        transaction records
data/raw/nodes/<run_id>_blocks.csv     block series
data/raw/nodes/<run_id>_resources.csv  1 Hz CPU / memory / disk / queue
data/raw/network/<run_id>_probes.json  RTT / jitter / loss, before-during-after
data/raw/manifests/<run_id>.json       run passport
data/raw/MANIFEST.sha256               hashes of every file above
```

The record schema is in `protocol/DATA_DICTIONARY.md`. The published
dataset carries pseudonymised identifiers only: no private keys, no internal
IP or MAC addresses, no payload that could expose user data.

---

## 11. Statistical plan

Transactions inside a run share a block, a consensus round and a disk
queue, so they are not independent replicates. **The run is the inferential
unit.** Each run is first reduced to p50/p95/p99, goodput, success rate,
p99 convergence and resource statistics; confidence intervals are built on
those run-level values.

The design is paired: within a `topology x load x repeat` stratum the
baseline C0 and the profile share a `trace_id`, so the difference is taken
run by run and the 95 % CI comes from a bootstrap over pairs with 10 000
replications and a fixed seed.

* **Primary endpoint** — difference in p99 of `T_visible,first` between a
  profile and C0, per `topology x load`.
* **Secondary endpoints** — p50/p95, `T_visible,all`, convergence, goodput,
  availability, queue slope, CPU, disk I/O.
* **Multiplicity** — raw effect and 95 % CI are always reported; the
  confirmatory family (the primary endpoint) additionally carries a
  Holm-corrected p-value.
* **Precision rule** — where the 95 % CI of the primary endpoint has a
  relative half-width above 10 %, add repeats in blocks of 5 up to 30, and
  apply the rule identically to every compared regime.

---

## 12. Stability and the best static configuration

| Criterion | Threshold |
| --- | --- |
| Successful and visible transactions | >= 99.5 % |
| Read-node consistency | 100 % of successful transactions |
| Queue slope | 95 % CI must not confirm positive accumulation |
| p99 second half vs first half | <= +20 %, and only when the change also exceeds one polling interval |
| Node health check | no loss longer than 5 s |
| CPU | not >= 95 % for 30 s together with a backlog |

The polling-interval floor on the drift rule is a deliberate refinement: a
p99 change smaller than the 25 ms client polling grid is a single
discretisation step, not a degrading regime. It is stated here, before the
data is inspected, and applied identically to every configuration.

`C_best` is chosen among the configurations that stay stable over the widest
contiguous load region; among those, the lowest mean p99 wins, and a rival
inside a +/-5 % practical-equivalence band is preferred when it costs less
CPU, less disk latency and lower `T_visible,all`. To avoid optimistic bias,
make the choice on a calibration series or a pre-defined data split and
confirm it on unused repeats.

Maximum sustainable load is reported under both pre-registered variants —
all repeats, and the majority rule. A disagreement between them marks a
boundary cell where the precision rule should add repeats before any claim
is made.

---

## 13. Reproducibility, safety, ethics

* Load is directed only at the own permissioned L1 and isolated RPC
  endpoints; the public Avalanche network is never used for high intensity.
* An external public-network reference, if retained, is a separate
  low-intensity observation with its date, RPC provider, plan, rate limit
  and ethical/financial clearance recorded.
* Private keys travel through a secret store or the environment and never
  reach JSONL, Git or the published dataset.
* Internal IP and MAC addresses, logins and user identifiers are
  pseudonymised; payloads carry no personal data.
* Every run has a manifest with SHA-256 of configs, code, traces and logs;
  timestamps are recorded in UTC alongside Europe/Kyiv.
* ACL/NAT/routes and the emergency stop are checked before every active
  run; results with an unplanned route failover are marked and kept out of
  the main series.
* Use of AI assistants for text, code or figure structuring is declared in
  the Acknowledgements per JTIT rules.

---

## 14. Threats to validity

**Internal.** Time of day, campus background traffic, VPN route changes,
thermal throttling, cache warm-up and unreset state can confound the block
interval effect. Controls: paired traces, blocked randomisation, resets and
health checks, identical versions and configs, and recorded background RTT
and resource use.

**Construct.** A receipt is not accessible state, hence the independent
read-back. But the first read may itself be the favourable case, hence
`T_visible,all` and `T_convergence` alongside it. The 25 ms polling interval
introduces a discretisation error of up to about one interval; it is stated
in Limitations and can be reduced with a WebSocket or event-driven method
after checking equivalence.

**External.** Two campus sites and one emulated region do not reproduce the
variability of a global network. Conclusions hold for the specific
Subnet-EVM version, the probe transaction, the gas/fee configuration, the
hardware and the workload.

**Statistical.** Millions of transactions do not substitute for independent
repeats. Bootstrapping individual transactions would produce artificially
narrow intervals. Comparing many `topology x load x profile` combinations
requires multiplicity control and effect sizes, not p-values alone.

---

## 15. Outstanding data

`protocol/DATA_REQUIRED.md` holds the checklist. `alp` refuses to label a
dataset `MEASURED` while it is unfilled, and every table and figure prints
the provenance of the dataset it was built from.
