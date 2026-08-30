# Inventory status - Gate 1

**STATUS: OPEN. `inventory.csv` contains no verified physical asset.**

Every row of `inventory.csv` except `SIL-CONTAINER` carries `verified_by = PENDING`,
because no inventory act exists. The `status` column separates three very different
kinds of claim, and the distinction is the whole point of this file.

| `status` value | Meaning | Rows |
|---|---|---|
| `VERIFIED_SIL_ONLY` | Actually executed and recorded in this deposit | 1 |
| `DECLARED_NOT_VERIFIED` | Named in the cyber-range description as existing, but never inventoried, so its model, revision, firmware, uplink and VLAN are unknown | 10 |
| `PROJECT_ONLY` | Described by the cyber-range document itself as a **project**, not as installed equipment | 1 (48 V DC circuit) |
| `NOT_PRESENT_IN_RANGE_DESCRIPTION` | Named in `Man-V3` Table 2 but absent from the cyber-range description entirely | 6 |

## The central discrepancy

`Man-V3` Table 2 and the UMSF cyber-range description describe **two different
facilities**:

| `Man-V3` Table 2 | UMSF cyber range |
|---|---|
| 12 emulated MQTT sensors | not mentioned |
| 4 x Raspberry Pi 5, K3s v1.30 | not mentioned |
| 3 cloud VMs, Kubernetes v1.30 | not mentioned |
| Eclipse Ditto 3.5 | not mentioned |
| Suricata 7.0 | not mentioned |
| Prometheus 2.53 / Grafana 11 | not mentioned |
| Kali attacker host | 25-seat Kali Linux classroom (site B) - the one genuine overlap |
| not mentioned | Keenetic Titan / Viva, UniFi CloudKey Gen1/Gen2, 54 access points |
| not mentioned | EcoFlow stations; projected 48 V DC circuit with BMS/ATS |
| not mentioned | site-to-site VPN, multi-WAN (3x1 Gbps + 2x100 Mbps) |

Only the Kali workstations appear in both. The cyber-range description is itself
careful here: it states that the five neural-network elements are a **recommended
superstructure** that "should be implemented and verified before the publication
asserts its actual operation", and that EcoFlow capacity and autonomy "should be
stated after control measurements".

## What must be produced before Gate 1 can close

1. A signed inventory act listing, for every asset: exact model, hardware revision,
   firmware/OS version, role, VLAN, uplink speed **measured** (not nominal), time
   source and logging state.
2. Measured throughput of each WAN link and of the VPN tunnel, with the protocol,
   cipher suite and MTU actually negotiated.
3. EcoFlow models, chemistry, nominal and usable capacity, and measured autonomy
   under a stated load.
4. For the 48 V circuit: whether it exists at all; if it does, the cell
   configuration (S/P), BMS model, charger rating, ATS model and acceptance-test
   report.
5. Confirmation, per asset, of whether the `Man-V3` Table 2 components exist
   anywhere in the facility. **Any component that cannot be shown to exist must be
   removed from the manuscript's empirical claims** and, if desired, described as
   future work.
6. Sanitised configuration exports with secrets removed, SHA-256 hashes in
   `checksums/SHA256SUMS`, and frozen software/container/model versions.
7. A physical and a logical topology diagram drawn from the act, not from the
   narrative description.

Until items 1-7 exist, `Man-V3` §2.6 ("Experimental Testbed") describes a facility
that has not been shown to exist, and every empirical number attributed to it is
unsupported.
