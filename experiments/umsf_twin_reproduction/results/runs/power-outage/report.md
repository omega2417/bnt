# Звіт синтетичного експерименту `power-outage`

## F.1. Ідентифікація
| Показник | Значення |
|---|---|
| experiment_id | power-outage |
| run_id | power-outage |
| mode | SIM |
| evidence_class | synthetic_demo |
| replicates | 1 |
| duration_s | 1200 |
| config_hash | e2dbbb728629a5cb839e541de0722a100c74496fcc92a35f60ae4618a8101088 |
| engine_source_hash | 2136f8f4be6e300c272a52056e15038260f33d67e0283cadde99939a09b24549 |

## F.3. Мережеві результати
### site_a
| Показник | Значення |
|---|---|
| steps | 1204 |
| availability_pct | 100.0 |
| rtt_mean_ms | 17.2765 |
| rtt_p95_ms | 19.191 |
| rtt_p99_ms | 20.0206 |
| loss_mean_pct | 0.17196 |
| throughput_mean_mbps | 136.3026 |
| offered_mean_mbps | 136.2946 |
| goodput_ratio | 1.0001 |
| failover_steps | 0 |
| failover_seconds | 0 |

### site_b
| Показник | Значення |
|---|---|
| steps | 1204 |
| availability_pct | 100.0 |
| rtt_mean_ms | 22.309 |
| rtt_p95_ms | 24.309 |
| rtt_p99_ms | 25.27 |
| loss_mean_pct | 0.29436 |
| throughput_mean_mbps | 77.7496 |
| offered_mean_mbps | 77.7106 |
| goodput_ratio | 1.0005 |
| failover_steps | 0 |
| failover_seconds | 0 |

## F.4. Енергетичні результати
| Показник | Значення |
|---|---|
| soc_start_pct | 81.99 |
| soc_end_pct | 80.78 |
| soc_drop_pct | 1.21 |
| soc_min_pct | 80.08 |
| autonomy_min_mean | 90.188 |
| autonomy_min_worst | 54.311 |
| battery_steps | 842 |
| load_shed_steps | 797 |
| protection_trip_steps | 53 |
| temp_max_c | 24.1 |
| cell_imbalance_max_mv | 120.0 |

## F.5. Виявлення
| Показник | Значення |
|---|---|
| tp | 0 |
| fp | 0 |
| tn | 2408 |
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
| soc_continuity | PASS | 0.27 | 0.5 |
| energy_sign | PASS | 0 | 0 |
| voltage_consistency | PASS | 0 | 0 |
| gap_blanking | PASS | 0 | 0 |

## F.9. Межа твердження
Ці результати характеризують поведінку програмної моделі за заданих припущень. Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або польову точність детекторів.
