# Zenodo deposit metadata

**Published record: <https://doi.org/10.5281/zenodo.22181264>** (version `2.0.0-experiment`).
The fields below are the ones used for that record; keep them in step with it.

Ready to paste. **Do not publish the record until `analysis/audit_provenance.py`
exits 0** — the archive is built by `analysis/make_zenodo_archive.sh`, which refuses
to package a failing audit.

---

## Title

```
Digital-twin cyber-resilience framework (DTCR): reference implementation,
pre-registered protocol, and a 1296-run software-in-the-loop evaluation
```

Shorter alternative, if the record title must fit on one line:

```
DTCR: a reference implementation and pre-registered software-in-the-loop
evaluation of a digital-twin cyber-resilience framework
```

**Do not** put "cyber range", "hardware-in-the-loop" or "testbed" in the title. The
physical campaign has not been run, and a title that implies otherwise
misrepresents the deposit.

## Resource type

Software. (The dataset, figures and documentation ship inside the same archive.)

## Version

`2.0.0-experiment`

## Publication date

`2026-08-30`

---

## Description / abstract — paste verbatim

Reproducibility deposit for a digital-twin-enabled cyber-resilience framework for
secure edge-cloud orchestration and data integrity, comprising a reference
implementation of the framework's mathematics, a frozen pre-registered
experimental protocol, and a fully executed software-in-the-loop (SIL) confirmatory
campaign.

**Scope statement.** The physical campaign on the laboratory cyber range has NOT
been performed. Its authorization, isolation and safety gate is unsigned and its
asset inventory is incomplete, so this deposit contains no measurement of physical
hardware; the `data/real/` directory is empty by design. Every deposited run
carries `data_origin = simulation` and must not be reported as a testbed result.

**Contents.** (1) `dtcr`, a reference implementation with one module per block of
the model: probabilistic block auditing, provenance-aware dynamic trust,
Mahalanobis anomaly scoring with chi-square calibration at the deployed feature
dimension, column-normalised dependency-graph risk propagation with an explicit
spectral-radius check, policy-constrained orchestration with hard admissibility
constraints and vector-valued capacity, and an RTO-bounded normalized resilience
index. (2) A frozen pre-registration with directional hypotheses, primary
endpoints, exclusion rules, a randomisation plan and a power analysis that fixes
the confirmatory sample size at 54 repetitions per cell. (3) A confirmatory
campaign of 1296 runs — six configurations (a manual baseline, an automated
playbook, and four ablations up to the full system) across four incident scenarios
at 54 repetitions each — blocked by seed so that every comparison is paired, with
0 exclusions, 318 right-censored runs, and a per-run gzipped evidence bundle
carrying a SHA-256 digest. (4) A statistical analysis reporting n, SD, IQR,
percentile-bootstrap confidence intervals, Hedges' g, Cliff's delta, risk
differences with Newcombe intervals, Holm correction over the pre-declared
hypothesis family, censoring accounting and sensitivity analysis. (5) An automatic
provenance and consistency audit of 23 checks that fails the build if a simulation
row is used to support a physical-hardware claim, if a number quoted in the report
cannot be recomputed from the run table, or if a re-execution is not byte-identical.
(6) A documented set of ten reproducible defects in the source manuscript, each
with quantitative evidence and a corrected formulation ready to paste.

**Selected findings.** Applying a two-degree-of-freedom chi-square threshold to the
nine-dimensional statistic actually deployed yields a 41.8% per-sample
false-positive rate against a nominal 1%. The manuscript's bounded anomaly
transform assigns a score of 0.985 to a median *healthy* asset at that dimension.
Its worked dependency-risk example reproduces only without the column
normalisation the text claims. Its orchestration objective compares an absolute
risk sum against normalised costs, so the balance between the two terms varies by a
factor of 3.5 between runs of the same deployment. A pooled mean detection latency
is not estimable, because the baseline configuration detects in 2 of 54 runs in one
scenario and 0 of 54 in two others. Null results are reported as found rather than
tuned away: no detection advantage under purely volumetric denial of service, no
graph benefit for a leaf-node integrity fault, and no measurable improvement in
action ranking from what-if planning in this environment. The manuscript's
analytical block-audit results and trust worked examples reproduce exactly.

**Reproduction.** The whole deposit regenerates deterministically in about two
minutes with `bash analysis/reproduce.sh` (Python 3.11, NumPy, SciPy, pandas,
Matplotlib; exact versions in `analysis/environment.lock`). Two independent
executions of the campaign are bit-identical, including all 1296 evidence-bundle
digests. To run the same analysis on physical data, place the measurements in
`data/real/` in the documented schema and re-run: no analysis code changes.

---

## Keywords

```
digital twin; cyber resilience; edge-cloud orchestration; data integrity;
anomaly detection; Mahalanobis distance; dependency-risk propagation;
policy-constrained orchestration; pre-registration; reproducibility;
software-in-the-loop; ablation study; cyber range
```

## Licences

- Software: **MIT**
- Dataset, figures and documentation: **CC BY 4.0**

## Related identifiers

| Relation | Identifier |
|---|---|
| `isSupplementTo` | the manuscript DOI, once assigned |
| `isNewVersionOf` | `10.5281/zenodo.22179426` — the previous release, whose data directory held a synthetic reference dataset that is **not** carried forward |
| `isSupplementedBy` | the repository URL cited in the manuscript |

## Contributors

Replace the placeholder author entry in `CITATION.cff` with the individual authors,
their ORCIDs and CRediT roles before publishing the record.

---

## Ukrainian version (for internal reporting; Zenodo record language stays English)

### Назва

```
Система кіберстійкості на основі цифрового двійника (DTCR): референсна реалізація,
попередньо зареєстрований протокол і програмний експеримент із 1296 запусків
```

### Анотація

Депозит відтворюваності для системи кіберстійкості на основі цифрового двійника,
призначеної для захищеної edge-cloud оркестрації та контролю цілісності даних.
Містить референсну реалізацію математичної моделі, заморожений попередньо
зареєстрований протокол експерименту та повністю виконану підтверджувальну
програмну (software-in-the-loop) кампанію.

**Межі застосовності.** Фізичний експеримент на лабораторному кіберполігоні **не
проводився**: дозвіл на роботи, перевірку ізоляції та безпеки не підписано,
інвентаризацію активів не завершено. Депозит не містить жодного вимірювання
фізичного обладнання; каталог `data/real/` порожній навмисно. Усі запуски мають
позначку `data_origin = simulation` і не можуть подаватися як результати стенду.

**Склад.** Референсна реалізація `dtcr` — по одному модулю на кожен блок моделі:
імовірнісний блоковий аудит, динамічна довіра з урахуванням provenance, оцінювання
аномальності за відстанню Махаланобіса з калібруванням за χ² для фактичної
розмірності ознак, поширення ризику графом залежностей із нормалізацією за
стовпцями та явною перевіркою спектрального радіуса, оркестрація з **жорсткими**
обмеженнями допустимості й векторною ємністю, а також індекс стійкості NRI,
обмежений RTO. Заморожена пререєстрація з напрямленими гіпотезами, первинними
метриками, правилами виключення, планом рандомізації та аналізом потужності, який
фіксує розмір вибірки — 54 повтори на комірку. Підтверджувальна кампанія з 1296
запусків: шість конфігурацій (ручне базове плече, автоматизований playbook і
чотири абляції до повної системи) × чотири сценарії інцидентів × 54 повтори,
блокована за початковим значенням генератора, тож усі порівняння парні; 0
виключень, 318 цензурованих справа запусків, для кожного запуску — стиснений
журнал доказів із SHA-256. Статистичний аналіз із n, SD, IQR, довірчими
інтервалами (percentile bootstrap), Hedges' g, Cliff δ, різницями часток з
інтервалами Ньюкомба, поправкою Голма, обліком цензурування та аналізом
чутливості. Автоматичний аудит походження з 23 перевірок, що зупиняє збірку, якщо
рядок симуляції використано для твердження про фізичне обладнання, якщо число зі
звіту не перераховується з таблиці запусків або якщо повторний запуск не є бітово
ідентичним. Перелік із десяти відтворюваних дефектів вихідного рукопису з
кількісними доказами та готовими до вставки виправленими формулюваннями.

**Окремі результати.** Застосування порога χ² із двома ступенями свободи до
фактично розгорнутої дев'ятивимірної статистики дає частку хибних спрацювань 41.8%
при номінальних 1%. Обмежене перетворення аномальності з рукопису присвоює оцінку
0.985 **медіанно здоровому** активу за цієї розмірності. Наведений у рукописі
приклад поширення ризику відтворюється лише **без** нормалізації матриці, яку
декларує текст. Цільова функція оркестрації порівнює абсолютну суму ризику з
нормованими витратами, тому баланс між доданками змінюється в 3.5 раза між
запусками того самого стенду. Усереднений час виявлення не є оцінюваним, бо базова
конфігурація виявляє інцидент у 2 з 54 запусків одного сценарію і в 0 з 54 у двох
інших. Нульові результати наведено як є, без підлаштування середовища: переваги
виявлення при суто об'ємній відмові в обслуговуванні немає, граф не дає виграшу для
листового вузла при порушенні цілісності, а what-if планування не покращує
ранжування дій у цьому середовищі. Аналітичні результати блокового аудиту та
приклади моделі довіри з рукопису відтворюються точно.

**Відтворення.** Депозит детерміновано регенерується приблизно за дві хвилини
командою `bash analysis/reproduce.sh`. Дві незалежні кампанії бітово ідентичні,
включно з усіма 1296 хешами журналів. Щоб виконати той самий аналіз на фізичних
даних, достатньо покласти вимірювання в `data/real/` за задокументованою схемою і
перезапустити — код аналізу не змінюється.

---

## After publication

1. The version DOI `10.5281/zenodo.22181264` is recorded in `CITATION.cff` and in
   `manuscript/manuscript_insert.md`. Confirm in a signed-out browser that it
   resolves to this version and not to the concept ("all versions") record, then
   fill the access date in the Data Availability statement.
2. Verify in a signed-out browser that the repository link in the manuscript shows
   this code and not an unrelated default branch (defect C10).
