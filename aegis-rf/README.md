# AEGIS-RF — гібридна байєсівська просторова ідентифікація Wi-Fi у КІІ

**Adversary-rEsistant Geolocation & Integrity for wi-fi Signals**

Прикладний демонстраційний **програмний проєкт за Розділом 1** дисертаційного
дослідження: просторова ідентифікація джерел IEEE 802.11 у критичній інформаційній
інфраструктурі (КІІ) зі злиттям **RSSI-радіокарти** та **FTM/RTT-дальнометрії**,
**робастністю** до навмисних маніпуляцій та **доказовою атрибуцією** для SOC/SIEM/SOAR.

> **Демонстраційні дані.** Усі числа характеризують синтетичну генеративну модель,
> параметри якої задані автором, а не реальні вимірювання. Пакет ілюструє методологію
> та перевіряє відтворюваність обчислень; він **не призначений** для експлуатації без
> валідації на реальних даних.

## Що реалізовано (за підрозділами розділу)

| Підрозділ | Компонент | Модуль |
|---|---|---|
| 1.1 Моделі загроз (rogue AP / evil twin / deauth) | Супротивник | `src/adversary.py` |
| 1.2 RSSI-fingerprinting, байєсівська локалізація | Середовище + радіокарта, RSSI-правдоподібність | `src/environment.py`, `src/localization.py` |
| 1.3 FTM/RTT-дальнометрія (802.11mc/az) | Модель дальності, її правдоподібність | `src/sensing.py`, `src/localization.py` |
| 1.4 Гібридне злиття, робастний інференс | Зважений добуток правдоподібностей + відсіювання викидів | `src/localization.py` |
| 1.5 Безпека, доказова атрибуція, SOC/SIEM | Spatial Attribution Record (JSON) | `src/attribution.py` |
| — Метрики, сценарії, оркестрація | Похибка/атрибуція + bootstrap-CI, прогін | `src/metrics.py`, `src/pipeline.py` |

## Структура

```
aegis-rf/
├── AEGIS_RF_Demo_Colab.ipynb                # модульний ноутбук (імпортує src/)
├── AEGIS_RF_Demo_Colab_selfcontained.ipynb  # Colab-версія (реконструює src/ через %%writefile)
├── src/                                      # пакет моделі (8 модулів)
├── tests/test_reproducibility.py            # 103 pytest-тести
├── requirements.txt · pytest.ini
├── LICENSE · CITATION.cff · .zenodo.json    # метадані для Zenodo
└── README.md
```

## Запуск

### Тести відтворюваності

```bash
cd aegis-rf
pip install -r requirements.txt
pytest -q          # 103 тести
```

Тести стверджують, що за `SEED = 80211` усі метрики (медіана/RMSE/P90 похибки,
zone-accuracy, Pd/FAR критичної зони) для **4 сценаріїв × 4 методів** збігаються з
еталонними значеннями **до 4 знаків**, конвеєр детермінований, а **робастне злиття
стійке до атак** (evil twin / deceptive ranging).

### Ноутбук

Локально:

```bash
jupyter nbconvert --to notebook --execute AEGIS_RF_Demo_Colab.ipynb
```

У Google Colab (модульний):

```python
!git clone https://github.com/omega2417/bnt.git
%cd bnt/aegis-rf
# Runtime → Run all
```

Або відкрийте **`AEGIS_RF_Demo_Colab_selfcontained.ipynb`** — він сам реконструює пакет
`src/` у середовищі Colab (`%%writefile`) і не потребує клонування.

## Основні результати (демонстраційні, seed=80211)

Медіанна похибка локалізації, м:

| Сценарій | RSSI | FTM | Наївне злиття | **Робастне злиття** |
|---|---|---|---|---|
| Без атак | 2.18 | 1.81 | 1.37 | **1.30** |
| Evil twin | 4.27 | 1.81 | 1.60 | **1.48** |
| Deceptive ranging | 2.18 | 4.26 | 3.47 | **1.67** |
| Deauth | 2.70 | 2.01 | 1.57 | **1.54** |

Головний висновок: **гібридне робастне злиття** зберігає точність там, де окрема
скомпрометована модальність завалює наївні методи.

## Артефакти для Zenodo

Ноутбук генерує (у `.gitignore`, створюються при запуску):
`results/metrics.csv`, `results/spatial_attribution_records.jsonl`,
`results/MANIFEST_sha256.json`, рисунки `figures/*.png` (320 dpi).

Депозит на Zenodo описують `.zenodo.json` (upload_type=software, MIT, keywords),
`CITATION.cff` та `LICENSE`.

Ліцензія: MIT.
