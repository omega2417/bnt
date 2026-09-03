# Звіт синтетичного експерименту `compound-challenge`

## F.1. Ідентифікація
| Показник | Значення |
|---|---|
| experiment_id | compound-challenge |
| run_id | compound-challenge |
| mode | SIM |
| evidence_class | synthetic_demo |
| replicates | 1 |
| duration_s | 700 |
| config_hash | 8eb0500ae69642d9fba3618b1721feda6fb7159a75db6258f430290654e20212 |
| engine_source_hash | 2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549 |

## F.3. Мережеві результати
### site_a
| Показник | Значення |
|---|---|
| steps | 703 |
| availability_pct | 91.3229 |
| rtt_mean_ms | 32.5337 |
| rtt_p95_ms | 95.8 |
| rtt_p99_ms | 97.5707 |
| loss_mean_pct | 0.27719 |
| throughput_mean_mbps | 134.2992 |
| offered_mean_mbps | 134.3061 |
| goodput_ratio | 0.9999 |
| failover_steps | 10 |
| failover_seconds | 10 |

### site_b
| Показник | Значення |
|---|---|
| steps | 703 |
| availability_pct | 100.0 |
| rtt_mean_ms | 41.9789 |
| rtt_p95_ms | 99.04 |
| rtt_p99_ms | 100.3086 |
| loss_mean_pct | 0.11944 |
| throughput_mean_mbps | 77.3375 |
| offered_mean_mbps | 77.2777 |
| goodput_ratio | 1.0008 |
| failover_steps | 0 |
| failover_seconds | 0 |

## F.4. Енергетичні результати
| Показник | Значення |
|---|---|
| soc_start_pct | 81.99 |
| soc_end_pct | 81.15 |
| soc_drop_pct | 0.84 |
| soc_min_pct | 81.06 |
| autonomy_min_mean | 90.343 |
| autonomy_min_worst | 54.951 |
| battery_steps | 422 |
| load_shed_steps | 427 |
| protection_trip_steps | 28 |
| temp_max_c | 23.9 |
| cell_imbalance_max_mv | 0.0 |

## F.5. Виявлення
| Показник | Значення |
|---|---|
| tp | 120 |
| fp | 0 |
| tn | 1225 |
| fn | 0 |
| precision | 1.0 |
| recall | 1.0 |
| f1 | 1.0 |
| false_alarm_rate_per_1k_steps | 0.0 |

## F.6. Data quality gates
| Gate | Результат | Значення | Поріг |
|---|---|---|---|
| completeness | PASS | 95.661 | 90.0 |
| time_monotonic | PASS | 0 | 0 |
| duplicate_rate | PASS | 0.427 | 5.0 |
| soc_continuity | PASS | 0.19 | 0.5 |
| energy_sign | PASS | 0 | 0 |
| voltage_consistency | PASS | 0 | 0 |
| gap_blanking | PASS | 0 | 0 |

## F.9. Межа твердження
Ці результати характеризують поведінку програмної моделі за заданих припущень. Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або польову точність детекторів.
