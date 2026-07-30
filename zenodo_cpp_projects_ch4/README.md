# Програмні проєкти до Розділу 4 — експериментальна валідація методології просторової атрибуції

Три самодостатні програмні проєкти мовою **C++17**, що реалізують ключові
обчислювальні ядра **Розділу 4** дисертації (експериментальний дизайн, метрики,
baseline-порівняння, калібрування, статистичний аналіз). Кожен проєкт:

- складається з **одного файлу** `src/main.cpp` без зовнішніх залежностей —
  компілюється й запускається **як є** на [OnlineGDB](https://www.onlinegdb.com),
  у `g++`/`clang++` (>= C++17) чи MSVC;
- містить **вбудовані синтетичні дані** та детермінований RNG (відтворюваний
  результат без введення);
- супроводжується `README.md`, `LICENSE` (MIT), `Makefile`, `CITATION.cff`
  та `.zenodo.json`; постачається окремим **ZIP-файлом** (тека `dist/`).

> Усі числа — **синтетична ілюстрація** методики оцінювання, а **не** результати
> дисертації. Розділ 4 прямо зазначає: числова перевага повного методу над
> baseline формулюється лише після заповнення таблиць реальними даними та
> перевірки ДІ, ефекту, множинності й failure strata. Робочі точки —
> **to_be_validated**.

---

## Склад

| # | Проєкт | Підрозділ | Ядро | ZIP |
|---|--------|-----------|------|-----|
| 1 | **Локалізаційні метрики** | §4.4 | MAE/median/RMSE, CDF/P95, HPD coverage & sharpness, zonal Brier/NLL, block bootstrap | `dist/project1_localization_metrics.zip` |
| 2 | **Калібрування та робастність** | §4.5 | NLL, Brier+Murphy, ECE/MCE, temperature scaling, degradation curves, recovery time | `dist/project2_calibration_robustness.zip` |
| 3 | **Baselines та статистика** | §4.3 | трилатерація/WKNN/probabilistic, block bootstrap CI, Wilcoxon, McNemar, Cliff's δ, Holm, Friedman/Nemenyi | `dist/project3_baselines_stats.zip` |

Проєкти утворюють логіку оцінювання Розділу 4: **baseline-порівняння зі
статистикою (§4.3) → локалізаційні метрики (§4.4) → калібрування й робастність
(§4.5)**. Спільний наскрізний принцип — **точкова точність відокремлена від
honesty і sharpness**, а нижча похибка сама по собі не є науковим твердженням
без ДІ, розміру ефекту та поправки на множинність.

## Швидкий старт

**OnlineGDB:** сайт → мова **C++** → вставте відповідний `src/main.cpp` → **Run**.

**Локально:**

```bash
cd project1_localization_metrics && make run
cd ../project2_calibration_robustness && make run
cd ../project3_baselines_stats && make run
```

## Відповідність підрозділам Розділу 4

| Метод / метрика | Підрозділ | Проєкт |
|---|---|---|
| MAE, median, RMSE, MAD, trimmed mean | §4.4.2 | 1 |
| CDF/CCDF, P90/P95/P99 | §4.4.3 | 1 |
| HPD coverage, sharpness, zonal Brier, NLL | §4.4.8 | 1 |
| block bootstrap CI (по блоках) | §4.3.8 | 1, 3 |
| NLL, Brier + Murphy decomposition, ECE/MCE | §4.5.2 | 2 |
| temperature scaling, reliability diagram | §4.5.1 | 2 |
| криві деградації, AUDC, recovery time | §4.5.9 | 2 |
| трилатерація, WKNN, probabilistic baselines | §4.3.2–4.3.5 | 3 |
| Wilcoxon, Hodges–Lehmann, McNemar, Cliff's δ | §4.3.8 | 3 |
| Holm–Bonferroni, Friedman/Nemenyi | §4.3.8 | 3 |

## Депонування на Zenodo

1. Замініть плейсхолдер автора (`[Author of the dissertation ...]`,
   `[Surname]`/`[Given name]`) у `.zenodo.json`, `CITATION.cff`, `LICENSE`.
2. Завантажте ZIP із теки `dist/` на <https://zenodo.org> (тип *Software*,
   ліцензія *MIT*); Zenodo зчитає `.zenodo.json` або заповніть метадані вручну.
3. Після публікації отримаєте **DOI** для посилання в тексті Розділу 4.

## Ліцензія

Усі три проєкти — MIT (див. `LICENSE` у кожній теці).
