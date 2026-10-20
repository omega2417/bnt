Table 6. Generated-code measurements: median [interquartile range] of 10 runs.

| Benchmark | Time | Allocations | Memory |
|---|---|---|---|
| Enum construction, R1 interface | 38.5 [37.7–39.2] ns/value | 1 per value | 16 B + 16.0 B heap |
| Enum construction, R2 flat struct | 11.3 [10.8–11.4] ns/value | 0 | 72 B |
| Enum construction, R3 compact struct | 10.0 [9.7–10.1] ns/value | 0 | 48 B |
| Exhaustive match, R1 | 13.2 [13.0–13.5] ns/value | 0 | – |
| Exhaustive match, R2 | 12.8 [12.7–12.9] ns/value | 0 | – |
| Exhaustive match, R3 | 13.1 [12.7–13.3] ns/value | 0 | – |
| Named/default call, GoNext lowering | 8.9 [8.4–9.0] ns/call | 0 | 0 B |
| Named/default call, configuration struct | 10.8 [10.7–10.9] ns/call | 0 | 0 B |
| Named/default call, functional options | 49.1 [48.9–49.7] ns/call | 1 | 48 B |
| Generic method + lambda (4096 elements) | 8.95 [8.51–9.42] µs | 1 | 32 KiB |
| Hand-written loop (4096 elements) | 9.17 [9.02–9.46] µs | 1 | 32 KiB |
| Extension method sum (4096 elements) | 1.272 [1.238–1.303] µs | 0 | 0 B |
| Hand-written sum (4096 elements) | 1.254 [1.220–1.287] µs | 0 | 0 B |
