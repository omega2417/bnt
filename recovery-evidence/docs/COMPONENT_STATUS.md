# Component status and claims boundary

For each element named in the article this table states whether it is implemented, how it
is verified, and whether the reported experiment exercises it. "Experiment" means the 13
conditions whose logs are in `results/`.

| Element | Implemented | Unit-tested | Integration-tested | Used in the experiment | Status of the evidence |
| --- | --- | --- | --- | --- | --- |
| Reference dependency map, `g`, `D`, `c` | yes | yes (exhaustive, 256 states) | yes | all conditions | exact by enumeration |
| Policies P0–P3, tie-break, sequential rule | yes | yes | yes | all conditions | deterministic; worked example and audit cases reproduced |
| Generator: transitions, notices, delays, non-substantive notices | yes | yes | yes | all conditions | synthetic; rates checked against parameters |
| Joint degradation of D and E | yes | yes (deterministic variant) | yes | C7 only | synthetic |
| Notice suppression | yes | yes | yes | C6 only | models missing information, not an adaptive adversary |
| Operator map error | yes | yes | yes | C8 only (F omitted from S2) | one form of error; spurious dependencies not studied |
| Less sharing (A2, F2) | yes | yes | yes | C9 only | confounded with lower `b/m`; compared within C9 only |
| Guarded test module (exact, immediate, equal cost) | yes | yes | yes | all conditions | assumption of the model, not a measurement |
| Evaluator: FASD, FUSD, spells, censoring | yes | yes | yes | all conditions | recomputed independently from the logs |
| Bootstrap intervals, MCSE | yes | yes | yes | all conditions | 10,000 resamples of whole trajectories |
| Re-check delay after a failed check | yes | via released tables | yes | all conditions with `b > 0` | exploratory, not pre-specified |
| Age cap or reserved periodic checks for standby nodes (Section 6.1) | **no** | — | — | — | recommendation only; not evaluated |
| Noisy, delayed or unequal-cost checks | **no** | — | — | — | named limitation |
| Multi-step or value-of-information policy; optimal benchmark | **no** | — | — | — | named limitation; P3 is a myopic heuristic and no distance to an optimum is reported |
| Combined stresses (e.g. C4 with C7) | **no** | — | — | — | conditions change one factor at a time |
| Calibration from organisational logs; field validation | **no** | — | — | — | required before operational use |

## What a result supports

| Output | It is | It is not |
| --- | --- | --- |
| FASD | share of service-days recorded ready while truly unready, per 100 observed service-days | a probability of failed recovery or of an incident |
| FUSD | share of service-days recorded unready while truly ready | a cost of unnecessary failover |
| Paired difference | mean over 300 synthetic trajectories that both policies replayed | an effect size for any real organisation |
| Bootstrap interval | Monte Carlo uncertainty of that mean in the stated model | a confidence interval for field performance |
| Checks per component | allocation of a simulated budget | measured audit effort |

The same author group designed the protocol, wrote the code and ran the experiment. The
package is released so that the run can be repeated and the rules changed by others.
