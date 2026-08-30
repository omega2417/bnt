# Topology actually exercised (software-in-the-loop)

This is the only topology for which measurements exist in this deposit. It is the
**model** used by `harness/environment.py`, not a physical network.

```
 12 sensors                edge tier                 cloud tier          service
 s00 ... s11
    |  |  |
    +--+--+---------> e0 (broker) ---> e1 (analytics) --------------+
                        |                                          |
                        +-----------> c0 (data store) --> c1 ------+--> svc
                                                                   |   (civil
       e2 (workload host) --------------------------------------->-+    service)
       e3 (workload host) --------------------------------------->-+
       c2 (twin core) ------------------------------------------->-+
```

Edge weights `W[i, j] > 0` mean "asset `j` depends on asset `i`" (the convention of
Eq. 9):

| from | to | weight |
|---|---|---|
| s00 … s11 | e0 | 1.00 each |
| e0 | e1 | 0.80 |
| e0 | c0 | 0.70 |
| e1 | svc | 0.60 |
| c0 | c1 | 0.50 |
| c1 | svc | 0.40 |
| e2 | svc | 0.30 |
| e3 | svc | 0.30 |
| c2 | svc | 0.10 |

Criticality weights `s_i`: sensors 0.30, e0 0.85, e1 0.70, e2/e3 0.55, c0 0.75,
c1 0.65, c2 0.60, svc 1.00.

The graph is acyclic, so the spectral radius of `lambda W^T` is 0 and Eq. (10)
converges unconditionally. This is a **property of this test graph, not a general
guarantee**: a real dependency graph with feedback (a service whose health feeds
back into a monitoring asset it depends on) can approach the convergence limit, and
`dtcr.graph_risk.propagate` raises rather than returning a value when it does. The
convergence margin is recorded for every run in `runs.csv`.

## Physical topology

Not available. See `../inventory_status.md`; Gate 1 is open.
