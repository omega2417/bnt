# Звіт синтетичного експерименту `wan-failover`

## F.1. Ідентифікація
| Показник | Значення |
|---|---|
| experiment_id | wan-failover |
| run_id | wan-failover |
| mode | SIM |
| evidence_class | synthetic_demo |
| replicates | 1 |
| duration_s | 600 |
| config_hash | 198020bb458c972c5b51d95f6bd52df03e17064062674a4e35133df95b7ff6a5 |
| engine_source_hash | 2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549 |

## F.3. Мережеві результати
### site_a
| Показник | Значення |
|---|---|
| steps | 602 |
| availability_pct | 100.0 |
| rtt_mean_ms | 19.54 |
| rtt_p95_ms | 24.0025 |
| rtt_p99_ms | 25.6455 |
| loss_mean_pct | 0.09032 |
| throughput_mean_mbps | 195.5416 |
| offered_mean_mbps | 195.4221 |
| goodput_ratio | 1.0006 |
| failover_steps | 15 |
| failover_seconds | 15 |

### site_b
| Показник | Значення |
|---|---|
| steps | 602 |
| availability_pct | 100.0 |
| rtt_mean_ms | 22.2265 |
| rtt_p95_ms | 24.38 |
| rtt_p99_ms | 25.27 |
| loss_mean_pct | 0.12264 |
| throughput_mean_mbps | 77.3684 |
| offered_mean_mbps | 77.2959 |
| goodput_ratio | 1.0009 |
| failover_steps | 0 |
| failover_seconds | 0 |

## F.4. Енергетичні результати
| Показник | Значення |
|---|---|
| soc_start_pct | 81.99 |
| soc_end_pct | 83.49 |
| soc_drop_pct | -1.5 |
| soc_min_pct | 81.98 |
| autonomy_min_mean | 92.245 |
| autonomy_min_worst | 88.21 |
| battery_steps | 0 |
| load_shed_steps | 0 |
| protection_trip_steps | 0 |
| temp_max_c | 23.4 |
| cell_imbalance_max_mv | 0.0 |

## F.5. Виявлення
| Показник | Значення |
|---|---|
| tp | 0 |
| fp | 0 |
| tn | 1204 |
| fn | 0 |
| precision | None |
| recall | None |
| f1 | None |
| false_alarm_rate_per_1k_steps | 0.0 |

## F.6. Data quality gates
| Gate | Результат | Значення | Поріг |
|---|---|---|---|
| completeness | PASS | 100.0 | 90.0 |
| time_monotonic | PASS | 0 | 0 |
| duplicate_rate | PASS | 0.332 | 5.0 |
| soc_continuity | PASS | 0.19 | 0.5 |
| energy_sign | PASS | 0 | 0 |
| voltage_consistency | PASS | 0 | 0 |
| gap_blanking | PASS | 0 | 0 |

## F.9. Межа твердження
Ці результати характеризують поведінку програмної моделі за заданих припущень. Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або польову точність детекторів.
