# Outstanding data checklist

Nothing in this repository can be reported as an experimental result until
these fields are filled from a real campaign. The list is machine-readable
in `alp.config.DATA_REQUIRED_FIELDS`, is emitted as
`results/csv/table_data_required.csv`, and is repeated at the end of every
generated report.

## Campaign record
- [ ] `campaign_date` — dates of the campaign and the record of conduct
- [ ] `responsible_person` — responsible person and the approvals obtained

## Software
- [ ] `avalanchego_version`, `avalanchego_commit`
- [ ] `subnet_evm_version`, `subnet_evm_commit`, `network_upgrade`
- [ ] `os_distribution`, `os_kernel`
- [ ] `solc_version`, `python_web3_version`

## Chain
- [ ] `chain_id`, `subnet_id`, `blockchain_id`
- [ ] `genesis_sha256`, `gas_limit`, `fee_config`
- [ ] `contract_address`, `contract_bytecode_sha256`, `abi_sha256`
- [ ] observed block interval of the stock profile C0

## Hardware and placement
- [ ] `validator_inventory` — NodeID, CPU, RAM, disk, NIC per validator
- [ ] `read_node_inventory` — the same for every read node
- [ ] the real number and placement of validators and read nodes
- [ ] models and firmware of Keenetic, CloudKey, access points, EcoFlow
- [ ] VLAN / ACL / NAT / Multi-WAN policy in force during the campaign

## Network
- [ ] `vpn_protocol`, cipher, `vpn_mtu`, routing mode
- [ ] `rtt_matrix_measured` — realised RTT/jitter/loss, before and after netem
- [ ] a third physical or cloud site, or an explicit statement that the
      three-region topology is emulated

## Timekeeping
- [ ] `clock_source` — chrony/NTP source
- [ ] `clock_max_offset_ms` — maximum offset observed, and the abort threshold

## Raw artefacts
- [ ] transaction JSONL of every run
- [ ] node logs and Prometheus exports
- [ ] network probe records
- [ ] the executed randomized schedule, including deviations

## Results
- [ ] measured p50 / p95 / p99, observed block interval, goodput
- [ ] maximum sustainable load, queue behaviour, CPU, disk I/O, failures
- [ ] read-node convergence
- [ ] 95 % confidence intervals, the rule for missing runs, exclusions and
      the deviation log

## Optional external baseline
- [ ] public Avalanche reference: RPC provider, date, rate, fees, raw logs,
      and the ethical/financial clearance for using it

## Publication
- [ ] repository DOI and dataset DOI (Zenodo)
- [ ] `CITATION.cff` completed with real author identifiers and ORCID
