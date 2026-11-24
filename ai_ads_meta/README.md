# ai_ads_meta

Збір і аналіз метаданих про рекламу в ШІ-системах (чат-боти, великі мовні
моделі, генеративний ШІ) та її вплив на користувачів. Лише стандартна
бібліотека Python 3.10+, ключі API не потрібні.

Запускати з кореня репозиторію.

## 1. Метадані публікацій

```bash
python -m ai_ads_meta run --out ai_ads_out --from-year 2018 --max-per-query 100
```

Кроки: пошук в OpenAlex, Crossref та arXiv за набором запитів → зведення до
єдиного формату → злиття дублікатів (за DOI, інакше за назвою) → кодування →
статистика. `collect` і `analyze` можна запускати окремо.

| Файл | Зміст |
|---|---|
| `records.jsonl` | усі унікальні записи з кодами |
| `relevant.csv` | релевантні записи (згадано і ШІ, і рекламу), відсортовані за релевантністю |
| `summary.json` | розподіли за роками, джерелами, країнами, кодами; таблиця «формат реклами × вплив» |
| `report.md` | той самий підсумок у вигляді таблиць + найцитованіші роботи |
| `features.csv` | бінарна матриця «публікація × категорія» (наприклад, для навчання структури байєсової мережі в BNT) |

Параметри: `--sources openalex,crossref,arxiv`, `--queries файл.txt` (один
запит на рядок; типові — у `sources.DEFAULT_QUERIES`), `--min-relevance N`,
`--mailto адреса` (необов'язково: OpenAlex і Crossref дають швидший доступ
клієнтам, що вказали контакт).

### Схема кодування (`taxonomy.py`)

- **ad_format**: conversational_ads, ai_generated_creative,
  targeting_personalization, recommendation_bias, disclosure_labeling,
  covert_dark_patterns
- **user_effect**: trust_credibility, manipulation_persuasion, privacy,
  purchase_behavior, autonomy_agency, wellbeing, fairness_vulnerable_groups,
  satisfaction_engagement, misinformation, social_norms_anomie
- **method**: experiment, survey, qualitative, system_audit, review,
  conceptual_legal
- **framing**: risk / benefit / mixed / neutral — за співвідношенням слів-маркерів

Коди присвоюються регулярними виразами за назвою та анотацією. Це інструмент
скринінгу й описового картування, а не заміна ручного кодування: перед
використанням у статті вибірку кодів варто перевірити вручну, а правила —
підлаштувати. Crossref часто не має анотацій, тож такі записи кодуються лише
за назвою.

## 2. Аудит відповідей чат-ботів

```bash
python -m ai_ads_meta audit -i ai_ads_meta/examples/chat_log.jsonl \
    --brands ai_ads_meta/examples/brands.txt --out ai_ads_out
```

Вхід — JSONL із полем `response` (необов'язково `id`, `model`, `prompt`,
`timestamp`). Для кожної відповіді визначаються: позначки розкриття реклами
(«sponsored», «реклама», «партнерське посилання»…), промо-лексика, посилання
з трекінговими параметрами (`utm_*`, `aff`, `ref`…), домени, згадки брендів зі
списку, відносна позиція першого сигналу та ознака `undisclosed_promo`
(комерційні сигнали без позначки розкриття). Результат: `audit.csv` і
`audit_summary.json` (частки загалом і за моделями). Дані обробляються
локально.

## Тести

```bash
python -m unittest discover -s ai_ads_meta/tests -t .
```

Тести працюють без мережі (відповіді API підставні).
