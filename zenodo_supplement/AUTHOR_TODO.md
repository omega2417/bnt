# Що зробити авторам перед завантаженням у Zenodo

Файл `replication-package_anonymised_v1.0.0.zip` містить повну структуру пакета за ТЗ:
код, документацію, кодування політик, кросвок і чернетку онлайн-додатка. **Самих даних
у ньому немає.** Сервери MRPiPS, World Bank і GeoNames недоступні з середовища, де готувався
пакет, а числа, яких немає в рукописі, вигадувати не можна. Цей файл у ZIP не входить, і
публікувати його не треба.

## 1. Дані (обов'язково)
- [ ] Покласти 88 таблиць MRPiPS у `data/raw/mrpips/`. Заповнити `source_inventory.csv`
      (url, download_date, `use`: 0 для заміненої версії таблиць 2021 р.) і `table_map.csv`
      (як читати кожен аркуш, див. README в тій самій папці). Якщо права на поширення
      таблиць сумнівні, лишити тільки inventory з URL і SHA-256.
- [ ] Знімки від 25.10.2026: `data/raw/worldbank/wdi_snapshot.csv`, `data/raw/geonames/`,
      `data/raw/restcountries/restcountries_all.json` з датою або версією.
- [ ] `data/raw/mrpips_reports/zus_stock.csv`: ряд 2013–2025. Окремо додати
      `holders_by_citizenship_2025.csv` для A10. У `report_extracts.csv` проставити сторінки,
      а також неокруглені числа декларацій і осіб за 2019 р. (коментар рецензента 8: 1.50 чи 1.51).
- [ ] Кросвок: запустити `01_import_mrpips.py`. Усі назви громадянств з
      `output/logs/unmatched_citizenships.csv` дописати в `polish_aliases`.
- [ ] Політики: точні дати набрання чинності в `data/policy/access_spells.csv` і
      `legal_acts.csv` (колонка `verify_note`). Для MD, GE, RU поки стоїть перше число місяця.
      У `document_duration.csv` вибрати вагу для повідомлень (зараз 12 міс.).

## 2. Відтворення
- [ ] `pip install -r environment/requirements.txt`, потім `python code/run_all.py`.
- [ ] Звірити з рукописом: 164 / 148 / 146 / 142 / 70 походжень; 2 184 спостереження;
      табл. 2–6. Якщо цифри розходяться, причина в дрібних рішеннях гармонізації (сепарація
      в PPML, трактування NA, дати). Python-код — незалежна реалізація, а не ваш
      оригінальний Stata-код. Якщо статтю рахували в Stata, покладіть `.do`-файли в
      `code/stata/` і вкажіть версії в `environment/software.md`.
- [ ] Після прогону `appendix/Online_Appendix.pdf` збереться з обчисленими таблицями
      автоматично. Позначка DRAFT і червоні `[run]` зникнуть, щойно буде порахована кожна таблиця.
- [ ] Перерахувати `CHECKSUMS.sha256`:
      `find . -type f ! -name CHECKSUMS.sha256 -print0 | sort -z | xargs -0 sha256sum > CHECKSUMS.sha256`.

## 3. Рукопис (за коментарями рецензента)
- [ ] Розд. 5.2: «199 draws» замінити на 999 + wild cluster score bootstrap (табл. A6);
      інтервал у табл. 3 (комент. 10).
- [ ] Табл. 5: p = (k+1)/(N+1) і N у кожному рядку (табл. A8, комент. 11). Для Грузії
      вказати, який рік є роком події 0 (комент. 15).
- [ ] Розд. 6.2 і 6.3.1: послатися на табл. A7 і A8 для 0.68/0.68, 0.66/0.68, «larger
      contrast» і «roughly a doubling» (комент. 12).
- [ ] Табл. 6: SE винести в A9, панелі позначити A/B (комент. 14).
- [ ] DAS і посилання на набір даних: шаблони з розд. 6–7 ТЗ.

## 4. Zenodo
- [ ] New upload → **Get a DOI now!** → вписати DOI в README.md, CITATION.cff, `.zenodo.json`
      і Online Appendix. Чернетку не публікувати.
- [ ] Рецензентам передавати тільки анонімізований ZIP (через систему журналу або OSF
      view-only), а не посилання на запис Zenodo.
- [ ] Після ухвалення статті: Creators з ORCID, DOI статті (`isSupplementTo`), прибрати з
      README розділи «Status of this copy» і «Completeness», опублікувати.
- [ ] Метадані з `.zenodo.json` вставити у форму. Ліцензії: CC BY 4.0 для даних і MIT для коду.
      Zenodo не розпаковує ZIP, тому README.md і Online_Appendix.pdf краще завантажити ще й
      окремими файлами.
