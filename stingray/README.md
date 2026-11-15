# 🛡️ Stingray — Офлайн-набір для захисту ПК

**Stingray** — офлайн-набір для перевірки, лікування і захисту ПК з Windows 10/11.
Працює без інтернету і без встановлення, з флешки, українською.
Кожна дія має пояснення і питає підтвердження.

## Можливості

### Перевірка ПК
- Чи працює антивірус
- Оновлення Windows і програм
- Небезпечні налаштування (UAC, RDP, SMBv1, LLMNR...)
- Підозрілий автозапуск, служби, драйвери, розширення браузерів
- Засоби віддаленого доступу
- Заборонені в Україні програми

**Результат** — зрозумілий HTML-звіт у браузері.

### Пошук шкідливого ПЗ
- Власна база понад 5,4 млн сигнатур (MD5/SHA256)
- YARA-рушій для поведінкового аналізу
- Інтеграція з ClamAV
- Виявлення з'єднань з серверами зловмисників
- Аналіз слідів атак у журналах

### Виправлення
- Карантин з можливістю повернути
- Вимкнення підозрілих служб
- Оновлення програм

Усе лише після вашого «так» і з резервною копією.

### Захист Windows
Понад 30 налаштувань безпеки:
- Вимкнення SMBv1, LLMNR, NetBIOS
- Вимкнення RDP, автозапуску USB
- Увімкнення UAC, фаєрвола, ASR-правил
- Журналювання PowerShell
- Вимкнення WSH та PowerShell v2
- І багато іншого...

## Встановлення

### З pip (рекомендовано)

```bash
pip install -e .
```

### Залежності

```bash
pip install -r requirements.txt
```

**Основні залежності:**
- `yara-python` — YARA-рушій для виявлення шкідливого ПЗ
- `psutil` — інформація про процеси та систему
- `jinja2` — генерація HTML-звітів

## Використання

### Командний рядок

```bash
# Перевірка стану системи
stingray check

# Сканування директорії
stingray scan C:\Users\Documents --signatures demo_signatures

# Сканувати всі файли (не лише виконувані)
stingray scan C:\Users --signatures demo_signatures --all-files

# Повна перевірка з HTML-звітом
stingray report --scan-path C:\Users --output report.html

# Карантин: перегляд
stingray quarantine list

# Карантин: відновлення
stingray quarantine restore --index 0

# Карантин: видалення
stingray quarantine delete --index 0
```

### Як бібліотека Python

```python
from stingray.signatures import SignatureDB
from stingray.scanner import StingrayScanner
from stingray.checker import SystemChecker
from stingray.report import generate_report

# Завантажити сигнатури
db = SignatureDB.load("demo_signatures")

# Сканувати директорію
scanner = StingrayScanner(db)
scan_report = scanner.scan_directory("C:\\Users\\Documents")

# Перевірити систему
checker = SystemChecker()
sys_report = checker.run_all_checks()

# Згенерувати звіт
generate_report(sys_report, scan_report, "report.html")
```

## Демонстрація в Google Colab

Відкрийте `stingray_demo.ipynb` в Google Colab для інтерактивної демонстрації:

1. Завантаження та сканування тестових файлів (EICAR, підозрілі скрипти)
2. YARA-аналіз з детальними результатами
3. Перевірка стану системи
4. Робота з карантином
5. Генерація HTML-звіту
6. Огляд налаштувань захисту Windows

> ⚠️ В Colab (Linux) Windows-специфічні перевірки будуть "пропущені".
> Повний функціонал доступний лише на Windows 10/11.

## Структура проєкту

```
stingray/
├── stingray/                  # Основний пакет
│   ├── __init__.py            # Версія
│   ├── scanner.py             # Сканер (хеші + YARA)
│   ├── signatures.py          # База сигнатур
│   ├── checker.py             # Перевірка системи
│   ├── quarantine.py          # Карантин файлів
│   ├── hardening.py           # Захист Windows (30+ налаштувань)
│   ├── report.py              # HTML-звіт
│   └── cli.py                 # CLI-інтерфейс
├── demo_signatures/           # Демо-сигнатури
│   ├── hashes.json            # MD5/SHA256 хеші
│   └── yara_rules/            # YARA-правила
│       ├── eicar.yar
│       ├── suspicious_scripts.yar
│       └── ransomware_indicators.yar
├── stingray_demo.ipynb        # Google Colab ноутбук
├── pyproject.toml             # Конфігурація пакету
├── requirements.txt           # Залежності
└── README.md                  # Ця документація
```

## Безпека

Stingray:
- Працює офлайн — жодних даних не передається назовні
- Кожна дія питає підтвердження
- Карантин замість видалення — завжди можна повернути
- Підписаний ключем для перевірки цілісності

## Ліцензія

MIT
