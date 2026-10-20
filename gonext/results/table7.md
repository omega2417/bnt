Table 7. Objects reclaimed while still referenced by live enum values (10 trials × 10,000 objects).

| Storage of the pointer payload | GC-visible | Reclaimed per trial (median) | Range |
|---|---|---|---|
| unsafe.Pointer slot (R3) | Yes | 0 | 0–0 |
| Interface value (R1) | Yes | 0 | 0–0 |
| uintptr word | No | 10,000 | 10,000–10,000 |
