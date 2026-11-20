"""LexViz - запуск на iPad одним натисканням.

Pythonista 3 / Pyto / a-Shell / Carnets: відкрийте цей файл і натисніть ▶ Run
(у a-Shell: `python3 run_ipad.py`).

Скрипт:
  1. перевіряє набір даних і методологічні правила (розділ 2.3 статті);
  2. перевіряє палітру на розрізнюваність при порушеннях кольоросприйняття;
  3. будує всі 8 рисунків у output/print (PNG, PDF, SVG);
  4. створює output/index.html - галерею, що відкривається в Safari / Файлах.

Налаштування - змінні нижче.
"""
import os
import sys
import time

DATASET = "data/ukraine_recovery_2026.yaml"   # можна вказати й .json
OUTDIR = "output"
DPI = 600                 # 600 - для MDPI; 200 - швидкий перегляд на iPad
FORMATS = ("png", "pdf", "svg")
FIGURES = None            # None = усі; або, наприклад, ["fig4_compliance_matrix"]

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # some app consoles run code without __file__
    HERE = os.getcwd()
os.chdir(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def main():
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("Потрібен matplotlib. Він є в Pythonista 3, Pyto, Carnets і Juno.")
        return 1
    from lexviz import DataError, build, load
    from lexviz.palette import report

    print("LexViz - перевірка даних:", DATASET)
    try:
        d = load(DATASET)
    except DataError as e:
        print("ПОМИЛКА ДАНИХ:", e)
        print("Виправте файл даних і запустіть знову.")
        return 2
    print("  OK: %d сфер, правила розділу 2.3 виконано" % len(d["areas"]))

    ok, text = report()
    print("Палітра (симуляція протанопії, дейтеранопії, тританопії):")
    print("  " + text.replace("\n", "\n  "))

    print("Побудова рисунків (%d dpi, %s) ..." % (DPI, ", ".join(FORMATS)))
    t0 = time.time()
    out = build(d, OUTDIR, FIGURES, dpi=DPI, formats=FORMATS)
    n = sum(len(v) for v in out.values())
    print("Готово за %.0f с: %d рисунків, %d файлів." % (time.time() - t0, len(out), n))
    gallery = os.path.join(HERE, OUTDIR, "index.html")
    print("Галерея:", gallery)
    print("Файли для видавця:", os.path.join(HERE, OUTDIR, "print"))
    _preview(gallery)
    return 0


def _preview(path):
    """Show the gallery where the app allows it (Pythonista); otherwise just print the path."""
    try:
        import console  # Pythonista
        console.quicklook(path)
        return
    except Exception:
        pass
    try:
        import webbrowser
        if sys.platform not in ("ios",):
            webbrowser.open("file://" + path)
    except Exception:
        pass


if __name__ == "__main__":
    code = main()
    if code:
        print("Завершено з кодом", code)
