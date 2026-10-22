# References (DOIs) and where each is used in the code

Every DOI cited in the article was traced to the concept it supplies. The table
shows which part of this package implements, depends on, or deliberately does
**not** implement that concept. DOIs are also listed as `references` in
`.zenodo.json`, `CITATION.cff` and `references.bib`.

| # | Reference | DOI | Role in this package |
|---|---|---|---|
| 3 | Somers et al. 2023, Digital-twin-based testing for CPS | [10.1016/j.infsof.2022.107145](https://doi.org/10.1016/j.infsof.2022.107145) | Evidence-level separation A/B/C; fidelity is tested, not assumed (`README`, notebook §1) |
| 4 | Wang et al. 2023, Survey on Metaverse security & privacy | [10.1109/COMST.2022.3202047](https://doi.org/10.1109/COMST.2022.3202047) | Trust layer beneath the immersive view: integrity, freshness (`twin.py: freshness`) |
| 5 | NIST CSF 2.0 | [10.6028/NIST.CSWP.29](https://doi.org/10.6028/NIST.CSWP.29) | Detect / respond / recover framing of the field protocol (`field_protocol/S1`) |
| 6 | NIST SP 800-160 Vol. 2 Rev. 1 | [10.6028/NIST.SP.800-160v2r1](https://doi.org/10.6028/NIST.SP.800-160v2r1) | Cyber-resiliency: anticipate/withstand/recover scenarios S4–S7 |
| 7 | NIST SP 800-61 Rev. 3 | [10.6028/NIST.SP.800-61r3](https://doi.org/10.6028/NIST.SP.800-61r3) | Alert tiering and human-in-the-loop response (no automatic remediation) |
| 8 | NIST AI RMF 1.0 | [10.6028/NIST.AI.100-1](https://doi.org/10.6028/NIST.AI.100-1) | Transparent, non-learned scoring; explanation = exact score decomposition (`detector.py`) |
| 9 | Sarhan et al. 2022, standard NIDS feature sets | [10.1016/j.bdr.2022.100359](https://doi.org/10.1016/j.bdr.2022.100359) | Fixed, documented 7-feature vector (`config.FEATURES`) |
| 10 | Barnard et al. 2022, Robust NIDS through XAI | [10.1109/LNET.2022.3186589](https://doi.org/10.1109/LNET.2022.3186589) | Feature-contribution explanation, top-3 hit rate (`detector.evaluate`, `benchmark`) |
| 11 | RFC 8032, EdDSA | [10.17487/RFC8032](https://doi.org/10.17487/RFC8032) | Ed25519 event and validator signatures (`crypto.py`, `gateway.py`, `ledger.py`) |
| 12 | FIPS 180-4, SHA-256 | [10.6028/NIST.FIPS.180-4](https://doi.org/10.6028/NIST.FIPS.180-4) | Payload hash, event hash chain, block hash, twin-state hash (`crypto.py`) |
| 14 | Chouliaras et al. 2021, Cyber ranges and testbeds | [10.3390/app11041809](https://doi.org/10.3390/app11041809) | Cyber range as controlled evaluation environment (`topology.py`, S1) |
| 15 | Vielberth et al. 2021, DT-based cyber range for SOC | [10.1007/978-3-030-81242-3_17](https://doi.org/10.1007/978-3-030-81242-3_17) | Related work — twin as training environment (not re-implemented) |
| 16 | Rebecchi et al. 2022, SPIDER 5G cyber range | [10.1109/WoWMoM54355.2022.00088](https://doi.org/10.1109/WoWMoM54355.2022.00088) | Related work (not re-implemented) |
| 17 | Zhou et al. 2023, DT cyber range for IIoT | [10.1109/MCE.2022.3203202](https://doi.org/10.1109/MCE.2022.3203202) | Related work (not re-implemented) |
| 18 | Mathur 2023, Reconfigurable DT for CI defense | [10.1109/MSEC.2023.3281272](https://doi.org/10.1109/MSEC.2023.3281272) | Related work; no CI-facility claim (`topology.py` note) |
| 19 | Park et al. 2022, Multi-cyber range | [10.3390/app122412546](https://doi.org/10.3390/app122412546) | Related work — orchestration out of scope |
| 20 | Fu et al. 2024, Disentangled orchestration | [10.1109/TDSC.2023.3303888](https://doi.org/10.1109/TDSC.2023.3303888) | Related work — orchestration out of scope |
| 21 | Sanz-Rodrigo et al. 2023, DT for 5G networks | [10.1109/ACCESS.2023.3267548](https://doi.org/10.1109/ACCESS.2023.3267548) | Topology-aware twin node model (`twin.py`, `topology.SENSORS`) |
| 23 | Rousseeuw & Croux 1993, Alternatives to the MAD | [10.1080/01621459.1993.10476408](https://doi.org/10.1080/01621459.1993.10476408) | Median/MAD with consistency factor 1.4826, Eq. (3) (`detector.RobustDetector.fit`) |
| 24 | Kumar et al. 2024, DT-enabled zero-touch network | [10.1016/j.future.2024.02.015](https://doi.org/10.1016/j.future.2024.02.015) | Closest related work; contrasted: admission-before-state instead of post hoc XAI |
| 25 | Neto et al. 2023, CICIoT2023 | [10.3390/s23135941](https://doi.org/10.3390/s23135941) | **Not used** — no signed envelopes/sequences/power fields (limitation) |
| 26 | Saito & Rehmsmeier 2015, PR plot vs ROC | [10.1371/journal.pone.0118432](https://doi.org/10.1371/journal.pone.0118432) | Precision/recall/F1 and AUPRC (`metrics.py`) |

References without DOI: [1] ISO/IEC 30173:2023; [2] ISO 23247-1:2021; [13] NIST
"The Cyber Range: A Guide" (2023); [22] MITRE ATT&CK Enterprise Matrix.

Note: DOI strings were taken verbatim from the manuscript. They could not be
resolved from the build environment (doi.org was not reachable), so please let
Zenodo's reference check or a manual click-through confirm them before deposit.
