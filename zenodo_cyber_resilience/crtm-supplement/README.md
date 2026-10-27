# CRTM — Cyber-Resilience Tuple Model (digital supplement)

Reference implementation, data and interactive notebook for the article

> **A Set-Theoretic Tuple Model with Level-Consistent Normalization and Non-Compensatory
> Aggregation for Assessing the Cyber Resilience of Critical Infrastructure.**
> [Author One], [Author Two], [Author Three]. *Information* (MDPI), 2026.
> Article DOI: *to be inserted*. Software DOI (Zenodo): *to be inserted*.

The package turns the definitions, propositions and theorems of the article into executable,
tested code and reproduces **every number, table and figure of the illustrative application**
(phishing attack, MITRE ATT&CK T1566, on the payment processing center of a bank, BNK_PAY).
`scripts/reproduce.py` compares the computed values with **107 values printed in the article**
and fails if any of them is not reproduced.

## Contents

```
crtm-supplement/
├── crtm/                     Python package (the model)
│   ├── scale.py              five-level linguistic scale, level map λ            (Def. 5)
│   ├── normalization.py      class tables ξ, n_{c,h}, anchored ν_ξ, Theorem 1,
│   │                         Corollary 1, grid consistency check              (Sec. 5)
│   ├── aggregation.py        additive, hard gate, power, capped operators,
│   │                         missing-metric enclosure, property probes        (Sec. 6)
│   ├── hierarchy.py          identifiers ι, techniques, projections, lattice ⊔/⊓,
│   │                         down-set encoding, Jaccard distance              (Sec. 3)
│   ├── metrics.py            metric descriptors, metric tuples, data loaders  (Sec. 4)
│   ├── evaluation.py         evaluation algorithm (Fig. 8), roll-up, profiles (Sec. 6.6–6.7)
│   ├── uncertainty.py        Dirichlet weight uncertainty, Proposition 7     (Sec. 6.5)
│   ├── sensitivity.py        response-time sensitivity, level thresholds      (Sec. 7.4)
│   └── figures.py            all supplementary figures (matplotlib)
├── data/
│   ├── phishing_metrics.csv  Table S2: 39 metrics, printed classes, anchors ξ, values, weights
│   └── scenarios.json        catalog technique sets and the DDoS / phishing projections (Fig. 4)
├── scripts/reproduce.py      reproduces Section 7; writes results/ and checks.csv
├── notebooks/
│   ├── CRTM_Colab.ipynb          interactive notebook (Google Colab / Jupyter), self-contained
│   └── CRTM_Colab_executed.ipynb same notebook with all outputs, for reading without running
├── results/                  Data S1 (results.json), checks.csv, tables/*.csv, figures/*.{png,svg,pdf}
├── tests/                    pytest suite: theorems, propositions and published numbers
├── tools/                    build_notebook.py, build_listing.py
├── docs/LISTING.pdf          program code listing with line numbers and SHA-256 digests
├── docs/LISTING.md           the same listing in Markdown
├── CITATION.cff  .zenodo.json  LICENSE  LICENSE-DATA  pyproject.toml  requirements.txt  Makefile
```

## Quick start

**Google Colab (no installation).** Open `notebooks/CRTM_Colab.ipynb` in Colab
(*File → Upload notebook*) and choose *Runtime → Run all*. The first cell unpacks the embedded
package and data, so nothing else has to be uploaded. Sliders let you change the number of
threat-intelligence sources, γ, ϑ and the response times; the sandbox scores your own metric.

**Locally.**

```bash
python -m pip install -r requirements.txt
python scripts/reproduce.py          # ~1 min; add --fast for 20,000 Monte Carlo samples
python -m pytest -q                  # 24 tests
jupyter lab notebooks/CRTM_Colab.ipynb
```

or `make all` (reproduce, test, rebuild notebook and listing).

## Using the library

```python
import crtm
t = crtm.ClassTable((180, 179, 90, 30, 10, 0))   # time to determine TI relevance, min
t.tabulated_level(25)        # 4  (above average, from the class table)
t.linear(25)                 # 0.9118 -> level 5 "high": inconsistent (Corollary 1)
t.anchored(25)               # 0.75   -> level 4: consistent by construction (Theorem 2)

actions = crtm.load_metrics()
r = crtm.evaluate_scenario(actions, method="anchored", operator="capped", theta=0.5)
r["profile"]                 # goal roll-ups (mean and minimum)
```

## What is reproduced

| Article | Quantity | Script check |
|---|---|---|
| §3.5, Fig. 4 | projections 9 / 7 actions, meet 4, join 12, Jaccard 1/3 and 13/36 | ✓ |
| §5.2, Cor. 1 | interval (10, 27] min of class-4 times mapped to "high" | ✓ |
| §5.3, Fig. 6 | 9 of 38 linear scores inconsistent, 0 anchored | ✓ |
| §7.1 | grid check of λ(ν_ξ(x)) = λ_ξ(x), 39 tables × 20,019 points | ✓ |
| Table 5 | UN.S1.A1: 0.9035 (H) vs 0.8558 (AA); equal weights; M1 = 0 | ✓ |
| Table 4, §7.3 | one TI source: gate 0.716, power 0.179, capped 0.500 | ✓ |
| §7.4, Fig. 10 | score ranges, max difference 0.100, thresholds 48.9 / 27.4 / 7.3 / 37.5 min | ✓ |
| §7.5, Fig. 11 | Dirichlet moments, P(high) 18.5 % / 9.5 % (α = 1), 2.9 % / 0.5 % (α = 4) | ✓ |
| Table 6, Fig. 12 | seven action scores, enclosure of CN.S2.A1, goal means and minima | ✓ |

Monte Carlo estimates use the article's seed 20261027 and 200,000 weight vectors. Results were
produced with Python 3.13, NumPy 2.5, SciPy 1.18 and Matplotlib 3.11.

## Data provenance and limitations

The metric definitions, class tables and example values come from the source study, which
specified them for an *illustrative* processing center; they are **not field measurements**,
and the numbers demonstrate the mathematics rather than assess a real organization.
One value (security software verified after the course of action, CN.S2.A1) is not reported.
`data/scenarios.json` contains the technique sets of the 12 actions shown in Figure 4 of the
article. The curated tabulation of all 140 CREF actions (Table S1, `stdm_catalog.csv`) is
supplied by the authors with the article's supplementary materials and is not duplicated here.

The figures of this supplement are redrawn from the code; they illustrate the same results as
the article figures and may differ from them in layout.

## License and citation

Code: MIT (`LICENSE`). Data, results and figures: CC BY 4.0 (`LICENSE-DATA`).
Please cite the article and this software record; see `CITATION.cff`.

---

### Коротко українською

Цифровий додаток до статті в журналі *Information* (MDPI): програмна реалізація теоретико-множинної
кортежної моделі оцінювання кіберстійкості критичної інфраструктури. Пакет `crtm` реалізує
індексацію ієрархії CREF, решітку проєкцій загроз, узгоджену з п'ятирівневою шкалою нормалізацію,
некомпенсаторну агрегацію (жорсткий стоп-фактор, степеневе дисконтування, обмежувальний
knockout-оператор), інтервальні оцінки для пропущених метрик і аналіз невизначеності ваг.
Скрипт `scripts/reproduce.py` відтворює всі 107 чисел ілюстративного прикладу (фішинг у
процесинговому центрі банку). Ноутбук `notebooks/CRTM_Colab.ipynb` запускається в Google Colab
без встановлення і містить інтерактивні повзунки. Лістинг програмного коду — `docs/LISTING.pdf`.
