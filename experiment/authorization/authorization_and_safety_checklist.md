# Authorization and safety checklist - Gate 0

**STATUS: OPEN. NOT SIGNED. NO PHYSICAL ACTIVITY HAS BEEN AUTHORISED OR PERFORMED.**

This document is the executable checklist for the physical campaign on the UMSF
laboratory cyber range. It is issued **empty of signatures on purpose**: nobody has
signed it, no window has been agreed, and no injection has been run on the
facility. Every line below must be completed and countersigned by two people
before a single active scenario is started.

The software-in-the-loop campaign reported in `docs/EXPERIMENT_REPORT.md` ran
entirely inside an isolated container with no network path to the university
network, and required none of the approvals below. That is why it is labelled
`data_origin = simulation` throughout and cannot substitute for any item here.

---

## 0.1 Roles - to be filled by the range owner

| Role | Name | Organisation | Signature | Date |
|---|---|---|---|---|
| Cyber-range owner | | | | |
| Responsible experiment lead | | | | |
| Operator | | | | |
| Independent observer | | | | |
| Responsible electrical engineer (required for S6 only) | | | | |
| Data-protection contact | | | | |

## 0.2 Scope of authorisation

| Item | Value | Verified by | Date |
|---|---|---|---|
| Exact start (UTC) | | | |
| Exact end (UTC) | | | |
| Sites in scope | | | |
| VLAN / VRF identifiers in scope | | | |
| Scenarios authorised (S1-S4, S5, S6) | | | |
| Explicitly out of scope | | | |
| Emergency-stop contact and channel | | | |

## 0.3 Isolation - all lines must read PASS before Gate 0 closes

| # | Control | Method of verification | Result |
|---|---|---|---|
| I1 | `attack` and `target` segments are in dedicated VLAN/VRF | switch and router configuration export | |
| I2 | Default-deny between the sandbox and every other segment | rule listing plus a negative connectivity test from inside the sandbox | |
| I3 | No egress from the attack segment to the Internet | attempted egress to a controlled external responder, expected to fail | |
| I4 | No path from the sandbox to any university production network | traceroute and firewall counters | |
| I5 | Targets are purpose-built VMs or containers with no personal or official data | image manifest plus a data-classification statement | |
| I6 | Snapshots taken of every target before the first injection | snapshot identifiers recorded in `inventory.csv` | |
| I7 | Snapshot restore rehearsed successfully at least once | restore log with timestamps | |
| I8 | Configuration backups taken and hashed | `inventory/sanitized_configs/` plus `checksums/SHA256SUMS` | |
| I9 | Time synchronisation from a controlled source on every node; clock offset recorded | NTP/PTP offset per node | |
| I10 | Logging enabled and exportable on every node in scope | sample export per node | |

## 0.4 Emergency stop

| # | Requirement | Result |
|---|---|---|
| E1 | A single documented action halts all injections | |
| E2 | The halt action was tested during the dry run, not only described | |
| E3 | The responsible person is reachable for the whole window | |
| E4 | Rollback to the pre-test state was demonstrated end to end | |

## 0.5 Electrical safety - required only if S6 is authorised

**No fault is to be injected into a live battery.** Short circuit, thermal runaway
and deep-discharge behaviour are to be studied on a bench tester, a current-limited
electronic load, or a simulator - never on the installed 48 V string.

| # | Requirement | Result |
|---|---|---|
| P1 | Manufacturer datasheets on hand for the battery, BMS, charger and ATS | |
| P2 | Responsible electrical engineer present for the whole window | |
| P3 | Certified PPE and insulated tooling in use | |
| P4 | Acceptance test of the 48 V circuit passed **before** any experimental switching | |
| P5 | Only nominal loss of input power is exercised; no forced fault on the string | |
| P6 | Current, voltage, temperature and BMS state logged throughout | |
| P7 | Documented abort criteria (temperature, cell delta, current) agreed in advance | |

## 0.6 Data governance

| # | Requirement | Result |
|---|---|---|
| D1 | Pseudonymisation plan for IP, MAC and user names written before capture | |
| D2 | Mapping between real and published identifiers held privately, never deposited | |
| D3 | No secrets, keys, credentials or certificates in any exported configuration | |
| D4 | Packet capture limited to the sandbox; personal traffic excluded by construction | |
| D5 | Retention period and deletion date agreed with the data-protection contact | |

## 0.7 Gate 0 decision

Gate 0 closes only when sections 0.1-0.6 are complete and **two** named people have
independently verified isolation, emergency stop and restore.

| Verifier | Name | Signature | Date |
|---|---|---|---|
| First | | | |
| Second | | | |

**Gate 0 verdict: NOT PASSED (unsigned).**
Consequently Gates 1-6 for the physical campaign are all OPEN, and no empirical
statement about the physical cyber range appears anywhere in this deposit.
