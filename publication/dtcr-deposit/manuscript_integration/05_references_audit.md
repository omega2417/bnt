# Bibliography audit and Related Work additions

## 1. Confirmed DOI mismatches (must be fixed before submission)

Each of these must be verified by hand against the primary source; the actions
are the reviewer's, restated with the corrected target where one is known.

| Ref | Printed DOI | Problem | Action |
|---|---|---|---|
| [16] Buja et al., "Cyber Resilience of Critical Infrastructures" | `10.3390/app131910592` | DOI resolves to a *saturated-claystone* paper, not cyber resilience | Replace with the correct systematic-review DOI, or drop the citation and cite a verified review |
| [20] Hosseini Shirvani et al., VM-migration survey | `10.1016/j.suscom.2020.100380` | DOI resolves to "RL-Sleep", unrelated | Verify against `10.1016/j.jksuci.2018.07.001` or locate the correct VM-migration survey DOI |
| [24] Ro et al., "Multi-Access Edge Computing Security: A Survey" | `10.1109/JIOT.2022.3176400` | DOI resolves to a UAV/edge-AI survey | Find the real MEC-security source or correct the metadata |
| [25] Attar & Anwar, IoT DDoS survey | `10.1016/j.comnet.2022.109553` | DOI belongs to de Neira et al., DDoS *prediction* | Correct author/title to match the DOI, or supply the correct DOI for the intended survey |

For **all 32 references**, verify by hand: authors, exact title, venue, year,
volume, issue, pages/article number, DOI, and that the cited claim is actually
supported by the source. Avoid large grouped citations without stating each
work's contribution.

## 2. Related Work additions (rewrite the research-gap claim)

The claim that no unified DT-security-orchestration loop exists must be
narrowed. Add and critically compare the closest integrated works, not just
surveys:

- Nguyen et al., 2026 — AI-driven digital-twin-based SOAR4BC — `10.1007/s10515-026-00612-1`
- "Digital Twins in Security Operations: State of the Art and Path Forward" — `10.1145/3746279`
- Kampourakis et al., 2025 — systematic review of DT-enabled incident detection and response — `10.1007/s10207-025-01113-0`
- SOAR4IoT
- Allison et al. — digital-twin-enhanced incident response
- DYNABIC and recent cybersecurity-digital-twin work

Reframe the contribution as **integration**, per §7.2 of the review:

> The contribution is not a new standalone audit, diffusion, or resilience
> formula, but a reproducible integration of cryptographically verified edge
> telemetry, dynamic trust, dependency-aware risk propagation, policy-constrained
> placement, and digital-twin-assisted recovery within one experimentally
> validated edge-cloud control loop.

## 3. Component-provenance table (new)

Add to Related Work or Methods, to separate borrowed, adapted and new elements:

| Component | Borrowed from | Adapted | New here | Validated by |
|---|---|---|---|---|
| Probabilistic block audit | Yang et al. [2] | challenge budget from Eq. (5) | integration into the control loop | `table_S4_integrity` |
| Dynamic trust | weighted/EWMA trust | provenance-derived inputs | coupling to orchestration | ablation B2 vs full |
| Dependency propagation | linear / Katz-like diffusion | security weighting, column normalisation | integration with recovery | incident-trace ranking (`table_S6`) |
| Placement constraints | secure-placement literature [1] | dynamic trust/risk admissibility | incident-driven placement | policy tests (`dtcr.orchestration`) |
| NRI | Cho et al. [5] | applied to this testbed | joint reporting with recovery | raw availability traces |
