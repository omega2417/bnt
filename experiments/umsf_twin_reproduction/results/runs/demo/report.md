# Звіт синтетичного експерименту `demo`

## F.1. Ідентифікація
| Показник | Значення |
|---|---|
| experiment_id | umsf-dt-demo-002 |
| run_id | demo |
| mode | SIM |
| evidence_class | synthetic_demo |
| replicates | 3 |
| duration_s | 900 |
| config_hash | 4e162d71f4b88bad4e910d57525f5b5365166152bf7fcea468c1b69f8921a740 |
| engine_source_hash | 2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549 |

## F.3. Мережеві результати
### site_a
| Показник | Значення |
|---|---|
| steps | 2709 |
| availability_pct | 96.124 |
| rtt_mean_ms | 23.3997 |
| rtt_p95_ms | 71.915 |
| rtt_p99_ms | 73.984 |
| loss_mean_pct | 0.19994 |
| throughput_mean_mbps | 178.1212 |
| offered_mean_mbps | 178.1095 |
| goodput_ratio | 1.0001 |
| failover_steps | 30 |
| failover_seconds | 30 |

### site_b
| Показник | Значення |
|---|---|
| steps | 2713 |
| availability_pct | 100.0 |
| rtt_mean_ms | 27.1114 |
| rtt_p95_ms | 76.714 |
| rtt_p99_ms | 78.4684 |
| loss_mean_pct | 0.28219 |
| throughput_mean_mbps | 83.0127 |
| offered_mean_mbps | 83.0013 |
| goodput_ratio | 1.0001 |
| failover_steps | 0 |
| failover_seconds | 0 |

## F.4. Енергетичні результати
| Показник | Значення |
|---|---|
| soc_start_pct | 81.99 |
| soc_end_pct | 82.99 |
| soc_drop_pct | -1.0 |
| soc_min_pct | 81.89 |
| autonomy_min_mean | 91.191 |
| autonomy_min_worst | 56.065 |
| battery_steps | 527 |
| load_shed_steps | 624 |
| protection_trip_steps | 42 |
| temp_max_c | 23.8 |
| cell_imbalance_max_mv | 85.0 |

## F.5. Виявлення
| Показник | Значення |
|---|---|
| tp | 181 |
| fp | 0 |
| tn | 4261 |
| fn | 875 |
| precision | 1.0 |
| recall | 0.1714 |
| f1 | 0.2926 |
| false_alarm_rate_per_1k_steps | 0.0 |

## F.6. Data quality gates
| Gate | Результат | Значення | Поріг |
|---|---|---|---|
| completeness | PASS | 98.063 | 90.0 |
| time_monotonic | PASS | 0 | 0 |
| duplicate_rate | PASS | 0.406 | 5.0 |
| soc_continuity | PASS | 0.24 | 0.5 |
| energy_sign | PASS | 0 | 0 |
| voltage_consistency | PASS | 0 | 0 |
| gap_blanking | PASS | 0 | 0 |

## F.9. Межа твердження
Ці результати характеризують поведінку програмної моделі за заданих припущень. Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або польову точність детекторів.
