"""Build the self-contained Colab notebook from canonical cells and local source."""
from pathlib import Path
import base64
import hashlib
import io
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def cell(kind, source, identity):
    result=dict(cell_type=kind,metadata={'id':identity},id=identity,source=source.splitlines(keepends=True))
    if kind=='code':result.update(execution_count=None,outputs=[])
    return result

def main():
    archive=io.BytesIO()
    paths=sorted((ROOT/'satqkd_sentinel').glob('*.py'))+sorted((ROOT/'tests').glob('*.py'))
    paths += [ROOT/'pyproject.toml',ROOT/'README.md',ROOT/'LICENSE']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            info=zipfile.ZipInfo(p.relative_to(ROOT).as_posix(),date_time=(2026,11,14,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes())
    payload=archive.getvalue()
    digest=hashlib.sha256(payload).hexdigest()
    setup='''# 1. Самодостатнє налаштування Google Colab / Jupyter. CPU достатньо.
import base64, hashlib, importlib, importlib.metadata, io, os, subprocess, sys, tempfile, zipfile
from pathlib import Path
if sys.version_info < (3, 10):
    raise RuntimeError("Потрібен Python 3.10 або новіший.")
# Do not upgrade Colab's preinstalled scientific stack unnecessarily.
requirements = {
    "numpy": "numpy>=1.26", "scipy": "scipy>=1.12", "pandas": "pandas>=2.1",
    "matplotlib": "matplotlib>=3.8", "sklearn": "scikit-learn>=1.4",
    "joblib": "joblib>=1.3", "pytest": "pytest>=8", "packaging": "packaging>=23",
    "ipywidgets": "ipywidgets>=7.7",
}
missing = [spec for module, spec in requirements.items() if importlib.util.find_spec(module) is None]
if missing:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing], check=True)
from packaging.requirements import Requirement
outdated = [spec for spec in requirements.values()
            if importlib.metadata.version(Requirement(spec).name) not in Requirement(spec).specifier]
if outdated:
    raise RuntimeError("Застарілі залежності: " + ", ".join(outdated) +
                       ". Оновіть їх через %pip install, перезапустіть сеанс і виконайте всі комірки.")
_SOURCE_ZIP = "PAYLOAD_TOKEN"
_SOURCE_SHA256 = "HASH_TOKEN"
raw = base64.b64decode(_SOURCE_ZIP, validate=True)
assert hashlib.sha256(raw).hexdigest() == _SOURCE_SHA256, "Embedded source checksum mismatch"
work_parent = Path("/content") if Path("/content").is_dir() else Path.cwd()
PROJECT_ROOT = Path(tempfile.mkdtemp(prefix="satqkd_2_0_2_", dir=work_parent)).resolve()
with zipfile.ZipFile(io.BytesIO(raw)) as source_zip:
    for member in source_zip.namelist():
        if Path(member).is_absolute() or ".." in Path(member).parts:
            raise ValueError("Unsafe embedded archive path")
    source_zip.extractall(PROJECT_ROOT)
# Rerunning this cell must never reuse another installed version of the project.
for name in list(sys.modules):
    if name == "satqkd_sentinel" or name.startswith("satqkd_sentinel."):
        del sys.modules[name]
sys.path.insert(0, str(PROJECT_ROOT))
importlib.invalidate_caches()
import satqkd_sentinel
assert Path(satqkd_sentinel.__file__).resolve().is_relative_to(PROJECT_ROOT)
assert satqkd_sentinel.__version__ == "2.0.2"
OUTPUT_DIR = PROJECT_ROOT / "results"
OUTPUT_DIR.mkdir()
print("Готово: SatQKD-Sentinel", satqkd_sentinel.__version__)
print("Код відновлено з ноутбука:", PROJECT_ROOT)
print("GPU, Google Drive та додаткові файли не потрібні.")
'''.replace('PAYLOAD_TOKEN',base64.b64encode(payload).decode()).replace('HASH_TOKEN',digest)
    original=json.loads((ROOT/'scripts/notebook_cells.json').read_text())
    imports=original[0]['source']
    imports=''.join(imports) if isinstance(imports,list) else imports
    imports=imports.replace("sys.path.insert(0, os.path.abspath('..'))",'assert PROJECT_ROOT.is_dir(), "Спочатку виконайте комірку налаштування."')
    imports+='''
# Capture every displayed figure as a PNG, while preserving inline display.
_original_show = getattr(plt.show, "_satqkd_original_show", plt.show)
_plot_counter = 0

def _show_and_save(*args, **kwargs):
    global _plot_counter
    for number in plt.get_fignums():
        _plot_counter += 1
        plt.figure(number).savefig(OUTPUT_DIR / f"figure_{_plot_counter:02d}.png", dpi=150, bbox_inches="tight")
    return _original_show(*args, **kwargs)

_show_and_save._satqkd_original_show = _original_show
plt.show = _show_and_save
'''
    original[0]['source']=imports.splitlines(keepends=True)
    for c in original:
        c['source']=''.join(c['source']).replace('v2.0.1','v2.0.2').splitlines(keepends=True)
        if c['cell_type']=='code':c.update(execution_count=None,outputs=[])
    intro='''# SatQKD-Sentinel 2.0.2 — Google Colab

**Завантажте лише цей `.ipynb` у Google Colab і виберіть Runtime → Run all (Середовище виконання → Виконати всі).** CPU достатньо; GPU не потрібний. Увесь код і тести вже вбудовані. Немає `../`, `git clone`, завантаження додаткового ZIP або підключення Drive.

Виконуйте комірки зверху вниз. Після скидання сеансу знову запустіть **Run all**. Наприкінці виконуються всі автоматичні тести, створюється ZIP результатів і з’являється кнопка завантаження. Перша комірка встановлює лише відсутні залежності; потрібен доступ до PyPI, якщо їх немає.

Це дослідницький симулятор на синтетичних даних. Finite-size оцінка не є доказом криптографічної безпеки.
'''
    checks='''# Автоматична перевірка всього проєкту в поточному середовищі.
import json, time
_test_env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONPATH=str(PROJECT_ROOT), MPLBACKEND="Agg")
_test_start = time.perf_counter()
_test_run = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                           cwd=PROJECT_ROOT, env=_test_env, capture_output=True, text=True)
_test_log = _test_run.stdout + _test_run.stderr
(OUTPUT_DIR / "tests.txt").write_text(_test_log, encoding="utf-8")
print(_test_log)
assert _test_run.returncode == 0, "Є невдалі тести — див. tests.txt; експорт зупинено."
assert np.isfinite(X_train).all() and np.isfinite(X_test).all()
assert len(list(OUTPUT_DIR.glob("figure_*.png"))) == 13
TEST_STATUS = {"returncode": _test_run.returncode, "seconds": round(time.perf_counter()-_test_start,2)}
print("Перевірки пройдено; 13 графіків збережено.")
'''
    export='''# Експорт уже обчислених результатів, без повторного навчання.
import html, joblib, shutil
from dataclasses import asdict
from satqkd_sentinel.cli import versions
summary_table(ev).to_csv(OUTPUT_DIR / "metrics.csv", index=False)
test_df.to_csv(OUTPUT_DIR / "telemetry.csv", index=False)
_predictions = test_df[["pass_id", "t_s", "label", "key_bits"]].copy()
_predictions["prediction"] = predict(results[best_method]["model"], X_test)
_predictions.to_csv(OUTPUT_DIR / "predictions.csv", index=False)
for name, frame in [("finite_key",df_fk),("geo_coverage",df_cov),("isl",df_isl),
                    ("daily_budget",df_budget),("block_policy",df_bp)]:
    frame.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
joblib.dump({"version":satqkd_sentinel.__version__,"sklearn_version":importlib.metadata.version("scikit-learn"),
             "feature_names":FEATURE_NAMES,"model":results[best_method]["model"]},OUTPUT_DIR / "model.joblib")
_run_info = {"version":satqkd_sentinel.__version__,"seed":42,"train_passes":30,"test_passes":20,
             "selected_method":best_method,"selection_basis":ev["selection_basis"],"tests":TEST_STATUS,
             "environment":versions(),"link_parameters":asdict(link),
             "classifiers":{name:{"macro_f1":float(data["metrics"]["macro_f1"]),
                                  "accuracy":float(data["metrics"]["accuracy"])} for name,data in results.items()}}
(OUTPUT_DIR / "summary.json").write_text(json.dumps(_run_info,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
_images = "".join('<img style="width:100%;height:auto;margin:12px 0" src="data:image/png;base64,' +
                  base64.b64encode(p.read_bytes()).decode() + '" alt="'+p.stem+'">'
                  for p in sorted(OUTPUT_DIR.glob("figure_*.png")))
_report = ('<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>SatQKD — Colab results</title><body style="max-width:1100px;margin:24px auto;padding:16px;font:16px system-ui">'
           '<h1>SatQKD-Sentinel 2.0.2 — результати</h1><p>Синтетичні дані. Модель обрана на окремій валідаційній вибірці.</p>'
           + summary_table(ev)[["method","macro_f1","accuracy"]].round(4).to_html(index=False)
           + '<h2>Автоматичні перевірки</h2><pre style="white-space:pre-wrap">'+html.escape(_test_log)+'</pre>'
           + _images + '</body></html>')
(OUTPUT_DIR / "report.html").write_text(_report,encoding="utf-8")
RESULTS_ZIP = Path(shutil.make_archive(str(PROJECT_ROOT / "satqkd_colab_results"), "zip", OUTPUT_DIR))
print("Результати:", RESULTS_ZIP)
print("Розмір ZIP:", round(RESULTS_ZIP.stat().st_size/1024/1024,2), "MiB")
'''
    download='''# Завантаження запускається лише натисканням кнопки, не блокує Run all.
from IPython.display import display, FileLink
try:
    from google.colab import files as _colab_files
except ImportError:
    display(FileLink(str(RESULTS_ZIP)))
else:
    import ipywidgets as widgets
    _download_button = widgets.Button(description="Завантажити результати", button_style="success", layout=widgets.Layout(width="260px"))
    _download_output = widgets.Output()
    def _download_results(_):
        with _download_output:
            _colab_files.download(str(RESULTS_ZIP))
    _download_button.on_click(_download_results)
    display(_download_button, _download_output)
'''
    cells=[cell('markdown',intro,'colab-start'),cell('code',setup,'colab-setup')]+original
    cells += [cell('markdown','## Перевірка всіх модулів, експорт і завантаження\n','checks-intro'),cell('code',checks,'run-tests'),cell('code',export,'export-results'),cell('code',download,'download-results')]
    for i,c in enumerate(cells):
        c.setdefault('id',f'satqkd-{i:03d}');c.setdefault('metadata',{})['id']=c['id']
    notebook=dict(nbformat=4,nbformat_minor=5,cells=cells,metadata={
        'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':'3.12'},
        'colab':{'name':'COLAB_START.ipynb','provenance':[]},
        'satqkd':{'version':'2.0.2','embedded_source_sha256':digest}})
    encoded=json.dumps(notebook,ensure_ascii=False,indent=1)+'\n'
    for p in (ROOT/'COLAB_START.ipynb',ROOT/'notebooks/demo_satqkd_sentinel.ipynb'):
        p.write_text(encoded,encoding='utf-8')
    print('Built self-contained notebooks; code cells:',sum(c['cell_type']=='code' for c in cells))

if __name__=='__main__':main()
