# Звіт синтетичного експерименту `cyber-campaign`

## F.1. Ідентифікація
| Показник | Значення |
|---|---|
| experiment_id | cyber-campaign |
| run_id | cyber-campaign |
| mode | SIM |
| evidence_class | synthetic_demo |
| replicates | 1 |
| duration_s | 700 |
| config_hash | 372361260f763a2f36aad7a7cf26fe7af429ad13287704589482f70fd5615deb |
| engine_source_hash | 2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549 |

## F.3. Мережеві результати
### site_a
| Показник | Значення |
|---|---|
| steps | 702 |
| availability_pct | 100.0 |
| rtt_mean_ms | 17.2664 |
| rtt_p95_ms | 19.28 |
| rtt_p99_ms | 20.1 |
| loss_mean_pct | 0.15285 |
| throughput_mean_mbps | 194.6381 |
| offered_mean_mbps | 194.5034 |
| goodput_ratio | 1.0007 |
| failover_steps | 0 |
| failover_seconds | 0 |

### site_b
| Показник | Значення |
|---|---|
| steps | 703 |
| availability_pct | 100.0 |
| rtt_mean_ms | 22.3496 |
| rtt_p95_ms | 24.379 |
| rtt_p99_ms | 25.268 |
| loss_mean_pct | 0.11979 |
| throughput_mean_mbps | 77.3381 |
| offered_mean_mbps | 77.2777 |
| goodput_ratio | 1.0008 |
| failover_steps | 0 |
| failover_seconds | 0 |

## F.4. Енергетичні результати
| Показник | Значення |
|---|---|
| soc_start_pct | 81.99 |
| soc_end_pct | 83.86 |
| soc_drop_pct | -1.87 |
| soc_min_pct | 81.98 |
| autonomy_min_mean | 92.308 |
| autonomy_min_worst | 88.21 |
| battery_steps | 0 |
| load_shed_steps | 0 |
| protection_trip_steps | 0 |
| temp_max_c | 23.5 |
| cell_imbalance_max_mv | 0.0 |

## F.5. Виявлення
| Показник | Значення |
|---|---|
| tp | 146 |
| fp | 0 |
| tn | 662 |
| fn | 597 |
| precision | 1.0 |
| recall | 0.1965 |
| f1 | 0.3285 |
| false_alarm_rate_per_1k_steps | 0.0 |

## F.6. Data quality gates
| Gate | Результат | Значення | Поріг |
|---|---|---|---|
| completeness | PASS | 100.0 | 90.0 |
| time_monotonic | PASS | 0 | 0 |
| duplicate_rate | PASS | 0.356 | 5.0 |
| soc_continuity | PASS | 0.19 | 0.5 |
| energy_sign | PASS | 0 | 0 |
| voltage_consistency | PASS | 0 | 0 |
| gap_blanking | PASS | 0 | 0 |

## F.9. Межа твердження
Ці результати характеризують поведінку програмної моделі за заданих припущень. Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або польову точність детекторів.
