# dt_power_hil — програмно-апаратний експеримент цифрового двійника живлення вузла зв’язку

Реалізація протоколу «Програмно-апаратний експеримент для цифрового двійника живлення вузла зв’язку» (v1.0) для рукопису
*Digital Twin of Power Supply for a Communication Node During Outages* (Applied Energy).

**Клас доказовості результатів у `results/`:** SIL з емуляцією апаратури (віртуальний стенд). Фізичних вимірювань немає.

| Частина | Де |
|---|---|
| Програмна: двійник, EMS, віртуальний стенд, аналіз | `dtpower/`, `scripts/`, `tests/`, `configs/` |
| Прошивка ESP32-S3 (ESP-IDF, не компілювалась) | `firmware/esp32_edge_guard/` |
| Апаратна: BOM на реальних елементах, схема, монтаж | `hardware/BOM_and_wiring.md` |
| Протоколи вимірювань П-1…П-7 | `hardware/measurement_protocols.md`, `results/protocols/` |
| Звіт у стилі Elsevier (UA) | `report/DT_HIL_Experiment_Report_Elsevier_UA.docx` |
| Веб-панель | `web/index.html` |

## Відтворення

```bash
pip install numpy scipy matplotlib python-docx pytest
python -m pytest -q tests                 # приймальні перевірки ПЗ (розд. 18.3 протоколу)
python scripts/run_campaign.py            # E00–E11 → results/ (≈ 80 с на 4 ядрах)
python scripts/make_figures.py            # results/figures/*.png|pdf
python scripts/make_protocols.py          # hardware/measurement_protocols.md
python scripts/make_report.py             # report/*.docx
python scripts/make_web.py                # web/index.html
```

## Перехід до фізичного стенда

1. Заповнити паспорт стенда та П-1 фактичними даташитами/шильдиками, замінити заповнювачі еталона в `configs/hardware_bench_12v.json`.
2. Замінити у `dtpower/bench.py` емульовані `BatteryPlant`/`PowerMonitorChannel`/`Channel` на драйвери RD6018 (Modbus), INA228-реєстратор і MQTT-клієнт; логіка `twin`, `ems`, `stats` не змінюється.
3. Зібрати й прошити `firmware/esp32_edge_guard`, повторити вектори E10 на цілі.
4. E00 → пілот E01–E05 → фіксація порогів → основна серія C0/C1/C2 (≥ 3 повтори) з `mode = "physical"`.
