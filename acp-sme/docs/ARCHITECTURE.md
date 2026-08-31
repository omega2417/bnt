# Architecture

## Edge-first design and the trust boundary

```
   business systems, identity and asset inventories, supplier records,
   metaverse-related edge services
                        |
                        |  read-only connectors, structured summaries only
                        v
   +---------------------------------------------------------------+
   |  LOCAL METADATA GUARD              (metadata_model.py)         |
   |    allowlist validation, banding, aggregation,                 |
   |    free-text rejection, provenance and quality,                |
   |    tenant-keyed pseudonyms, retention deadlines                |
   +---------------------------------------------------------------+
                        |  minimized business-state vector
                        v
   +---------------------------------------------------------------+
   |  ANALYSIS CORE                                                 |
   |    material-change detector  Eq. (1), (2)      (detector.py)   |
   |    typed capability traversal                  (crosswalk.py)  |
   |    exact resource-constrained selection Eq. (3), (4)           |
   |                                                (selector.py)   |
   +---------------------------------------------------------------+
                        |  explainable profile proposal
                        v
   ================ HUMAN APPROVAL BOUNDARY ========================
                        |
                        v
   +---------------------------------------------------------------+
   |  VERSIONED PROFILE LEDGER                      (profile.py)    |
   |    approve / defer / reject / request evidence,                |
   |    hash-chained versions, replay, rollback                     |
   +---------------------------------------------------------------+
```

Business content and direct identifiers never cross the guard. Only an explainable
proposal reaches the approval boundary, and only an authorized person crosses it.

## How local-first processing is enforced (R2)

The package performs **no network I/O at all**. There is no HTTP client, no socket, no
telemetry, no phone-home. This is a structural property, not a configuration setting:

```bash
grep -rE "import (socket|http|urllib|requests)|urlopen" src/    # returns nothing
```

`CONTRIBUTING.md` makes adding one a rejected change.

## Data flow through one adaptation cycle

1. **Validate.** A connector record is checked against the allowlist, the deny list,
   provenance and freshness rules. A prohibited field fails closed and is reported; it is
   never silently dropped.
2. **Aggregate.** Accepted observations become the tenant-local business-state vector.
   Unknown and stale evidence is deliberately *excluded* from the vector and surfaced
   separately, so the detector treats it as uncertainty rather than as a settled value.
3. **Detect.** Equation (2) fires on a critical predicate, a two-of-three persistent
   above-threshold distance, or the periodic timer.
4. **Traverse.** The typed capability graph resolves affected capabilities and their
   standards provenance across all three frameworks.
5. **Select.** Equation (4) is solved exactly over the 919 dependency-valid subsets within
   the approved budget.
6. **Explain.** A proposal is built carrying trigger, rationale, delta, provenance,
   prerequisites, burden, confidence, alternatives, expiry and rollback implications.
7. **Decide.** An authorized approver approves, defers, rejects or requests evidence.
   Anything but approval leaves the Current Profile untouched.
8. **Record.** An approval appends an immutable, hash-chained version with its evidence.

## Why the selector is exhaustive rather than heuristic

With 14 capabilities there are 16,384 candidate subsets, of which 919 are
prerequisite-closed. Enumerating them costs microseconds, so the prototype solves
Equation (4) **exactly**. Two consequences matter for the article's claims:

- Budget feasibility and prerequisite satisfaction are *invariants*, not success rates.
  `selector.assert_invariants` is called at every selection in the simulator.
- The reported coverage differences cannot be artifacts of a search heuristic converging
  differently under different conditions. All three conditions use the identical selector;
  only the reassessment timing differs.

This also satisfies R8: the core needs deterministic rules and a small exact optimizer, not
a data lake or a model-training platform.

## Self-protection posture (Section 6.1)

The protector holds business dependencies, profile gaps, supplier categories, resource
limits and decision history, so it must be **less privileged than the systems it observes**:

| Property | How this package reflects it |
| --- | --- |
| Read-only connectors | The guard only accepts records; nothing writes back to a source |
| No autonomous remediation | No code path implements a safeguard |
| Signed, versioned packs | Every pack carries a version constant; `CONTRIBUTING.md` requires dual approval for critical mapping changes |
| Hash-chained ledger | `ProfileLedger.verify_chain` detects a silent edit of decision history |
| Rollback | `ProfileLedger.rollback` appends a new version; history is never edited |
| Last approved profile survives an outage | The ledger is the source of truth; a missing connector yields `UNKNOWN`, not a recomputed profile |
| Separation of duties | `Role` distinguishes connector, analyst, approver and auditor |

## Staged deployment (Section 6.3)

1. **Baseline** — appoint a profile owner, approve scope, record the Current Profile and
   resource envelope, pin the standards and crosswalk versions.
2. **Observe** — connect one asset source and one identity source through the guard; verify
   exclusions, provenance, deletion and missingness behavior before expanding.
3. **Recommend** — run the detector in shadow mode, compare proposals with manual decisions,
   calibrate materiality and nuisance thresholds, document rejected recommendations.
4. **Govern** — enable signed approvals, evidence tasks, versioning, rollback, pack
   maintenance and periodic independent review; preserve a deterministic fallback mode.

A production release should add connector conformance tests, an SBOM, signed and staged
updates, encrypted backups, tenant isolation, recovery exercises and audit export. It
should **not** add autonomous remediation merely to shorten the recommendation delay: the
decision object and the accountable approval are the governance contribution.
