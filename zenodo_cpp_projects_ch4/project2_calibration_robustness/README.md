# Проєкт 2 (Розділ 4). Калібрування невизначеності та робастність (§4.5)

**Uncertainty Calibration and Robustness Evaluation**

Референсна реалізація підрозділу **4.5** (пп. 4.5.1–4.5.2 калібрування та
NLL/Brier/ECE; п. 4.5.9 криві деградації й recovery time). Програма мовою
**C++17** без зовнішніх залежностей, орієнтована на **OnlineGDB** і будь-який
`g++`/`clang++` (>= C++17) чи MSVC.

---

## 1. Частина A — імовірнісне калібрування (§4.5.1–4.5.2)

Для зональної ймовірності рішення (передбачена `P[джерело у критичній зоні]`
проти бінарного результату) обчислюються:

- **NLL** (proper score) з фіксованим clipping-epsilon у manifest;
- **Brier score** + **декомпозиція Мерфі**: `Brier = reliability − resolution + uncertainty`;
- **ECE** та **MCE** на **адаптивних (equal-count)** бінах;
- **calibration slope/intercept** — логістична регресія результату на `logit(p)`
  (ідеал: slope=1, intercept=0);
- **reliability diagram** (ASCII);
- **temperature scaling**: скаляр `T>0` навчається на **validation**-поділі
  (мінімізація NLL, golden-section), застосовується до **test** — ECE/NLL
  до та після, без зміни ranking моделей і topology мод.

> ECE подається **разом** із NLL/Brier, бо залежить від binning (§4.5.2).

## 2. Частина B — криві деградації та recovery (§4.5.9)

Stress-фактор зростає від 0 до пікового рівня й потім знімається; відстежуються:
метрика якості (тут — похибка HPD coverage відносно номіналу), **decision tier**
(AUTO/VERIFY/HiL), **AUDC** (area under degradation curve), **breakpoint**
(перехід у небезпечну зону) та **recovery time** (повернення в calibration
envelope). **Graceful degradation** — монотонна, обмежена втрата якості з
розширенням невизначеності й контрольованим відновленням, а не бінарне
«витримав/не витримав».

## 3. Очікуваний результат (фрагмент)

```
  [uncalibrated]  NLL=0.6278  Brier=0.2137  ECE=0.0827  MCE=0.2031
        calibration slope=0.5783  intercept=-0.1105   (over-confident)
-- fitted temperature on VALIDATION split: T = 1.747 --
  [temp_scaled]   NLL=0.5958  Brier=0.2054  ECE=0.0280  MCE=0.1020
        calibration slope=1.0101 ...
  danger breakpoint at step : 3   recovery time : 3 steps to re-enter AUTO envelope
```

Зауваження: у декомпозиції Мерфі `reliability − resolution + uncertainty` може
незначно відрізнятися від прямого Brier — різниця дорівнює середній
внутрішньобіновій дисперсії прогнозів (наслідок equal-count binning), а не
помилці обчислення.

## 4. Запуск на OnlineGDB

<https://www.onlinegdb.com> → **C++** → вставте `src/main.cpp` → **Run**
(введення не потрібне; RNG детермінований).

## 5. Локальна збірка

```bash
make run
# або: g++ -std=c++17 -O2 src/main.cpp -o calibration_robustness && ./calibration_robustness
```

## 6. Наукові застереження

Синтетичні числа — **ілюстрація**, не результати дисертації. Калібрувальний
трансформ навчається лише на validation, має власний ID і не змінює ranking без
документування (§4.5.1). Робочі точки — **to_be_validated**.

## 7. Ліцензія

MIT (див. `LICENSE`).
