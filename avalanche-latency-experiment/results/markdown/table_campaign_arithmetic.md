### Campaign arithmetic, equations (1)-(4)

_Provenance: DERIVED.  Not a measurement of the cyber range._

| quantity | formula | expansion | value | unit | equation | value_class |
| --- | --- | --- | --- | --- | --- | --- |
| N_runs | N_C * N_T * N_lambda * N_r | 5 * 3 * 5 * 3 | 225.00 | runs | 1 | DERIVED |
| t_run | warmup + measure + drain | 5 + 20 + 5 | 30.00 | s | 2 | DERIVED |
| T_wall,min | N_runs * t_run | 225 * 30 | 6750.00 | s | 3 | DERIVED |
| T_wall,min | N_runs * t_run / 3600 | 6750 / 3600 | 1.88 | h | 3 | DERIVED |
| N_TX | measure_s * sum(lambda) * N_C * N_T * N_r | 20 * 775 * 5 * 3 * 3 | 697500.00 | tx | 4 | DERIVED |
