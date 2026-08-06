# Scenario library

The twin ships 12 versioned scenarios spanning the ten lab works plus red-team negative tests. Each is also exported as YAML under configs/scenarios/.

| ID | Lab | Targets | Weather | Faults | Focus |
| --- | --- | --- | --- | --- | --- |
| `S01_baseline_clear` | ЛР-3 | 3 | clear | 0 | Baseline — clear weather, 3 targets |
| `S02_time_calibration` | ЛР-1 | 2 | clear | 0 | Time calibration stress (clock drift) |
| `S03_multitarget_crossing` | ЛР-4 | 4 | clear | 0 | Multi-target crossing (ID-switch stress) |
| `S04_sensor_dropout` | ЛР-5 | 3 | clear | 1 | Fault tolerance — radar dropout |
| `S05_packet_loss` | ЛР-5 | 3 | clear | 1 | Fault tolerance — network packet loss |
| `S06_domain_rain` | ЛР-6 | 3 | rain | 0 | Domain shift — heavy rain |
| `S07_domain_night` | ЛР-6 | 3 | night | 0 | Domain shift — night operations |
| `S08_redteam_spoof` | ЛР-5 | 3 | haze | 1 | Red-team — spoofed telemetry |
| `S09_swarm_dense` | ЛР-4 | 6 | haze | 0 | Dense swarm — 6 targets |
| `S10_degradation` | ЛР-5 | 3 | clear | 1 | Sensor degradation — EO noise burst |
| `S11_silent_glider` | ЛР-2 | 3 | clear | 0 | Low-observable silent glider |
| `S12_calibration_focus` | ЛР-7 | 4 | haze | 0 | Uncertainty calibration mission |

## Domain randomisation

Any scenario can be expanded into a family of related missions with
`ust_fuse.domain.randomize_scenario`, perturbing weather, clutter, noise and
detection probability while preserving the scientific structure (ЛР-6).

## Adding your own

Scenarios are plain `ScenarioConfig` dataclasses (or YAML). The proposal's LLM
"scenario generator" (section 5) is meant to emit exactly this JSON/YAML: UAV
classes, trajectories, weather, faults, metrics and risks.