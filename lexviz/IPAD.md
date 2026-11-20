# LexViz на iPad

Архів уже містить **готові рисунки** (`output/`), тож переглянути результат можна навіть без Python.
Щоб змінювати дані й перебудовувати рисунки, потрібен застосунок із Python і matplotlib.

## 1. Розпакувати
1. Збережіть `LexViz_iPad.zip` у застосунок **Файли** (наприклад, «На iPad»).
2. Торкніться архіву — iPadOS розпакує його в папку `lexviz`.

## 2. Переглянути готові рисунки (без Python)
Відкрийте `lexviz/output/index.html` → «Поділитися» → «Відкрити в Safari» (або просто перегляд у «Файлах»).
PNG/PDF для журналу — у `output/print/`, архів PNG 600 dpi для MDPI — `output/figures_png_600dpi.zip`.

## 3. Запустити програму

### Варіант A — Pythonista 3 (рекомендовано)
1. Pythonista → бокова панель → **External Files → Open…** → виберіть папку `lexviz`
   (або скопіюйте папку в «Pythonista 3» у «Файлах»).
2. Відкрийте `run_ipad.py` і натисніть **▶**.
3. Після збірки галерея відкриється автоматично.

### Варіант B — Pyto
1. Pyto → **Open** → виберіть `lexviz/run_ipad.py` (дозвольте доступ до папки).
2. Натисніть **▶**. Рисунки з’являться в `lexviz/output/`.

### Варіант C — Carnets або Juno (Jupyter)
Відкрийте `LexViz_iPad.ipynb` із папки `lexviz` і виконуйте клітинки по черзі (Shift+Enter).
Ноутбук показує рисунок просто в документі та демонструє роботу валідатора.

### Варіант D — a-Shell
```
cd ~/Documents/lexviz      # або: pickFolder і виберіть lexviz
python3 run_ipad.py
```
(Працює, якщо у вашій версії a-Shell доступний matplotlib.)

## 4. Змінити дані
- Основний файл — `data/ukraine_recovery_2026.yaml` (редагується в Pythonista, Pyto, Textastic, Runestone тощо).
- Якщо у застосунку немає модуля PyYAML, програма автоматично читає `data/ukraine_recovery_2026.json`.
  У такому разі редагуйте JSON-файл і вкажіть його в `run_ipad.py`: `DATASET = "data/ukraine_recovery_2026.json"`.
- Помилка в даних зупиняє збірку з поясненням, наприклад:
  `ПОМИЛКА ДАНИХ: state_aid: C2 not met must be rated 'misaligned by derogation'`.

## 5. Порада щодо швидкодії
Збірка 8 рисунків у 600 dpi на iPad триває приблизно від півхвилини до кількох хвилин.
Для швидкого перегляду поставте в `run_ipad.py` `DPI = 200`, а для подання до журналу поверніть `DPI = 600`.
