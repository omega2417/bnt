# `data/real/` — intentionally empty

This directory is reserved for the **confirmatory dataset of the physical UMSF
cyber-range campaign**, whose rows will carry `data_origin = real_testbed_confirmatory`.

It is empty because that campaign has not been run. Gate 0 (authorization,
isolation, safety) is unsigned; Gate 1 (inventory) is not done. See
`../../authorization/authorization_and_safety_checklist.md` and
`../../inventory/inventory_status.md`.

An empty directory here is a deliberate, checkable statement: the deposit contains
no physical-testbed measurement, and `analysis/audit_provenance.py` verifies that
no claim about physical hardware is backed by a simulation row.

When the physical campaign is run, place `runs.csv` and `raw/<run_id>/` here in the
schema of `../../processed/data_dictionary.md`, then rerun
`bash ../../analysis/reproduce.sh`. The analysis code does not change.
