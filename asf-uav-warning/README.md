# ASF-UAV-Warning — пакет відтворюваності

Демонстраційна Monte Carlo модель агентного мультисенсорного виявлення БпЛА та
публічного оповіщення. Пакет відтворюваності до статті:

> O. Korchenko, D. Prokopovych-Tkachenko, A. Desiatko, I. Azarov, O. Galushchenko, M. Mormul.
> **Agentic Multisensor System for Early Unmanned Aircraft Detection and Public Warning.**
> *Artificial Intelligence* (ISSN 2710-1673), 2026.

> **Демонстраційні дані.** Усі числа характеризують синтетичну генеративну модель,
> параметри якої задані авторами, а не реальні вимірювання. Пакет ілюструє методологію
> та перевіряє відтворюваність обчислень.

## Структура

```
asf-uav-warning/
├── ASF_UAV_Warning_Demo_Colab.ipynb   # тонкий оркестратор: викликає src/ і відображає результати
├── src/
│   ├── asf_simulation.py               # генеративна модель, події, оцінки архітектур, латентності
│   ├── metrics.py                      # пороги, Таблиця 4 + bootstrap CI, Pd за дальністю/умовами, абляція, часовий резерв
│   └── make_figures.py                 # усі рисунки (inline, 320 dpi)
├── tests/
│   └── test_reproducibility.py         # pytest: метрики Таблиці 4 збігаються з опублікованими до 4 знаків
├── requirements.txt
└── pytest.ini
```

Раніше вся логіка жила у комірках ноутбука. Тепер її винесено у пакет `src/`, тож її
можна **тестувати автономно** і **перевикористовувати** поза Colab.

## Запуск

### Тести відтворюваності

```bash
cd asf-uav-warning
pip install -r requirements.txt
pytest -q          # 29 тестів
```

Тести стверджують, що за `SEED = 20260` усі метрики Таблиці 4
(`precision, pd, f1, far, roc_auc, brier, latency_median_s, latency_p95_s`)
збігаються з опублікованими значеннями **до 4 знаків після коми**, а також що
конвеєр детермінований (повторний запуск дає біт-у-біт ті самі числа).

### Ноутбук

Локально:

```bash
cd asf-uav-warning
jupyter nbconvert --to notebook --execute ASF_UAV_Warning_Demo_Colab.ipynb
```

У Google Colab:

```python
!git clone https://github.com/omega2417/bnt.git
%cd bnt/asf-uav-warning
# далі Runtime → Run all
```

Ноутбук створює каталоги `data/`, `results/`, `figures/` з таблицями, рисунками
(320 dpi) і файлом контрольних сум `results/MANIFEST_sha256.json`. Ці каталоги
внесено до `.gitignore` як згенеровані артефакти.

## Використання пакета з коду

```python
from src import asf_simulation as sim_mod
from src import metrics as met

sim = sim_mod.simulate(seed=20260)
table4, thresholds = met.compute_metrics_table(sim)
print(table4.round(4))
```

Ліцензія: MIT.
