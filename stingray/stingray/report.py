"""Генерація HTML-звіту для перегляду у браузері."""

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

from .checker import CheckStatus, SystemCheckReport
from .scanner import ScanReport

REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stingray — Звіт безпеки</title>
<style>
:root {
  --bg: #0f172a; --fg: #e2e8f0; --card: #1e293b;
  --ok: #22c55e; --warn: #f59e0b; --crit: #ef4444; --skip: #64748b;
  --accent: #3b82f6; --border: #334155;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 24px; }
.container { max-width: 900px; margin: 0 auto; }
h1 { font-size: 2rem; margin-bottom: 8px; }
.subtitle { color: #94a3b8; margin-bottom: 32px; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }
.summary-card { background: var(--card); border-radius: 12px; padding: 20px; text-align: center; border: 1px solid var(--border); }
.summary-card .number { font-size: 2.5rem; font-weight: bold; }
.summary-card .label { color: #94a3b8; margin-top: 4px; }
.ok .number { color: var(--ok); }
.warn .number { color: var(--warn); }
.crit .number { color: var(--crit); }
h2 { margin: 32px 0 16px; font-size: 1.4rem; border-bottom: 2px solid var(--accent); padding-bottom: 8px; }
table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border); }
th { background: var(--card); color: #94a3b8; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }
td { background: var(--card); }
.badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
.badge-ok { background: #16532d; color: var(--ok); }
.badge-warn { background: #713f12; color: var(--warn); }
.badge-crit { background: #7f1d1d; color: var(--crit); }
.badge-skip { background: #1e293b; color: var(--skip); }
.badge-clean { background: #16532d; color: var(--ok); }
.badge-malicious { background: #7f1d1d; color: var(--crit); }
.footer { margin-top: 48px; text-align: center; color: #475569; font-size: 0.85rem; }
</style>
</head>
<body>
<div class="container">
  <h1>🛡️ Stingray — Звіт безпеки</h1>
  <p class="subtitle">{{ hostname }} &middot; {{ timestamp }}</p>

  <div class="summary">
    <div class="summary-card ok"><div class="number">{{ ok_count }}</div><div class="label">Без проблем</div></div>
    <div class="summary-card warn"><div class="number">{{ warn_count }}</div><div class="label">Попередження</div></div>
    <div class="summary-card crit"><div class="number">{{ crit_count }}</div><div class="label">Критичні</div></div>
    <div class="summary-card"><div class="number">{{ scanned_files }}</div><div class="label">Файлів просканувано</div></div>
  </div>

  {% if checks %}
  <h2>Перевірка системи</h2>
  <table>
    <tr><th>Перевірка</th><th>Статус</th><th>Деталі</th></tr>
    {% for c in checks %}
    <tr>
      <td>{{ c.name_uk }}</td>
      <td><span class="badge badge-{{ c.status }}">{{ c.status_label }}</span></td>
      <td>{{ c.message }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}

  {% if scan_results %}
  <h2>Результати сканування</h2>
  <table>
    <tr><th>Файл</th><th>Статус</th><th>Загроза</th></tr>
    {% for r in scan_results %}
    <tr>
      <td style="word-break:break-all;">{{ r.file_path }}</td>
      <td><span class="badge badge-{{ 'malicious' if r.is_malicious else 'clean' }}">{{ 'Загроза' if r.is_malicious else 'Чисто' }}</span></td>
      <td>{{ r.threat_name or '—' }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}

  {% if threats_found > 0 %}
  <h2>⚠️ Виявлені загрози ({{ threats_found }})</h2>
  <table>
    <tr><th>Файл</th><th>Загроза</th><th>Метод</th></tr>
    {% for r in threats %}
    <tr>
      <td style="word-break:break-all;">{{ r.file_path }}</td>
      <td><span class="badge badge-crit">{{ r.threat_name }}</span></td>
      <td>{{ r.detection_method }}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}

  <div class="footer">Stingray v1.0.0 — Офлайн-набір для захисту ПК</div>
</div>
</body>
</html>
"""


STATUS_LABELS = {
    CheckStatus.OK: "Добре",
    CheckStatus.WARNING: "Увага",
    CheckStatus.CRITICAL: "Критично",
    CheckStatus.SKIPPED: "Пропущено",
}

STATUS_CSS = {
    CheckStatus.OK: "ok",
    CheckStatus.WARNING: "warn",
    CheckStatus.CRITICAL: "crit",
    CheckStatus.SKIPPED: "skip",
}


def generate_report(
    system_report: SystemCheckReport,
    scan_report: ScanReport,
    output_path: str | Path,
) -> Path:
    output_path = Path(output_path)
    template = Template(REPORT_TEMPLATE)

    checks_data = []
    for c in system_report.checks:
        checks_data.append({
            "name_uk": c.name_uk,
            "status": STATUS_CSS[c.status],
            "status_label": STATUS_LABELS[c.status],
            "message": c.message,
        })

    threats = [r for r in scan_report.results if r.is_malicious]

    html = template.render(
        hostname=system_report.hostname,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        ok_count=system_report.ok_count,
        warn_count=system_report.warning_count,
        crit_count=system_report.critical_count,
        scanned_files=scan_report.scanned_files,
        checks=checks_data,
        scan_results=[
            {"file_path": r.file_path, "is_malicious": r.is_malicious,
             "threat_name": r.threat_name}
            for r in scan_report.results
        ],
        threats_found=scan_report.threats_found,
        threats=[
            {"file_path": r.file_path, "threat_name": r.threat_name,
             "detection_method": r.detection_method}
            for r in threats
        ],
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path
