**Ablation study (change relative to full framework).**

| Configuration | Detection F1 | Attribution macro-F1 | Leaf accuracy | Contained<impact |
| --- | --- | --- | --- | --- |
| full | 0.816 | 0.792 | 0.979 | 0.583 |
| no_calibration | 0.816 (+0.000) | 0.698 (-0.095) | 0.982 (+0.003) | 0.583 (+0.000) |
| no_cross_vehicle | 0.816 (+0.000) | 0.805 (+0.012) | 0.979 (+0.000) | 0.542 (-0.042) |
| no_fusion | 0.770 (-0.046) | 0.792 (+0.000) | 0.979 (+0.000) | 0.583 (+0.000) |
| no_hierarchy | 0.816 (+0.000) | 0.899 (+0.107) | 0.993 (+0.014) | 0.625 (+0.042) |
| no_safe_mask | 0.816 (+0.000) | 0.792 (+0.000) | 0.979 (+0.000) | 0.583 (+0.000) |
