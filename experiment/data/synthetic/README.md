# `data/synthetic/` — intentionally empty

The synthetic reference dataset shipped with the previous Zenodo release is NOT
carried forward. It existed to make the analysis runnable in the absence of data,
and its presence alongside empirical claims is precisely the problem flagged as B9
in `../../docs/issue_evidence_correction_matrix.md`.

The analysis pipeline no longer needs it: `harness/campaign.py` regenerates the
full simulation dataset deterministically in about 40 seconds.
