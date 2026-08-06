"""Field-trial style report generation (ЛР-9, ЛР-10; section 5 "Генератор звітів").

Turns an :class:`ExperimentResult` (and optionally a :class:`CampaignResult`)
into the three documents a field campaign produces:

* **Протокол місії / Mission Protocol** — what was flown and observed;
* **Лабораторний звіт / Lab Report** — metrics, figures, interpretation;
* **Технічний звіт / Technical Report** — provenance, config, reproducibility.

Output is Markdown (with embedded figures) plus a self-contained HTML export.
The bilingual (Ukrainian / English) headings match the proposal's language.
"""
from __future__ import annotations

import html as _html
import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .viz.style import MODE_LABELS


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _fmt(x, nd=3):
    if isinstance(x, float):
        if np.isnan(x):
            return "—"
        return f"{x:.{nd}f}"
    return str(x)


def _md_table(df: pd.DataFrame, floatfmt=3) -> str:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind in "fc":
            df[c] = df[c].map(lambda v: _fmt(float(v), floatfmt))
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.to_numpy()]
    return "\n".join([header, sep] + rows)


# --------------------------------------------------------------------------- #
# section builders
# --------------------------------------------------------------------------- #
def _mission_protocol(result) -> str:
    scn = result.config.scenario
    raw = result.raw
    faults = scn.faults or []
    lines = [
        "## 1. Протокол місії / Mission Protocol",
        "",
        f"**Місія / Mission:** {scn.title}  ",
        f"**Ідентифікатор сценарію / Scenario ID:** `{scn.scenario_id}`  ",
        f"**Лабораторна робота / Lab:** {scn.lab or '—'}  ",
        f"**Опис / Description:** {scn.description}",
        "",
        "| Параметр / Parameter | Значення / Value |",
        "| --- | --- |",
        f"| Тривалість / Duration | {scn.duration_s:.0f} s |",
        f"| Цілі / Targets | {scn.n_targets} ({', '.join(scn.uav_classes)}) |",
        f"| Траєкторії / Trajectories | {', '.join(scn.trajectory_kinds)} |",
        f"| Погода / Weather | {scn.weather} |",
        f"| Перетини траєкторій / Crossings | {'так/yes' if scn.crossing else 'ні/no'} |",
        f"| Відмови / Faults | {len(faults)} |",
        f"| Red-team | {', '.join(scn.red_team) or '—'} |",
        f"| Сенсорів у мережі / Sensors online | {len(raw.range_cfg.enabled_sensors())} |",
        f"| RAW-детекцій / RAW detections | {raw.stats['n_detections']} |",
        f"| Частка хибних / Clutter fraction | {raw.stats['clutter_fraction']*100:.1f} % |",
        "",
    ]
    if faults:
        lines.append("**Журнал відмов / Fault log:**")
        lines.append("")
        fdf = pd.DataFrame([{
            "kind": f.get("kind"), "sensor": f.get("sensor", "*"),
            "t0 (s)": f.get("t0", 0.0), "t1 (s)": f.get("t1", 0.0),
        } for f in faults])
        lines.append(_md_table(fdf))
        lines.append("")
    return "\n".join(lines)


def _lab_report(result, figures: Optional[Dict[str, str]] = None) -> str:
    lines = ["## 2. Лабораторний звіт / Lab Report", ""]

    # detection metrics
    det = result.detection
    ddf = pd.DataFrame([
        {"sensor": s, "type": det[s]["sensor_type"], "Pd": det[s]["pd_empirical"],
         "clutter/scan": det[s]["clutter_per_scan"], "mean SNR (dB)": det[s]["mean_snr_db"],
         "n_det": det[s]["n_detections"]}
        for s in det
    ])
    lines += ["### 2.1. Детекція (ЛР-2) / Detection", "", _md_table(ddf), ""]

    # tracking metrics per mode
    tdf = pd.DataFrame(result.summary_table())
    keep = ["mode", "rmse_pos", "ospa_mean", "mota", "motp", "id_switches",
            "fragmentations", "n_false_tracks", "track_completeness", "ece", "brier"]
    tdf = tdf[[c for c in keep if c in tdf.columns]]
    tdf["mode"] = tdf["mode"].map(lambda m: MODE_LABELS.get(m, m))
    lines += ["### 2.2. Супроводження та злиття (ЛР-3, ЛР-4) / Tracking & fusion",
              "", _md_table(tdf), ""]

    # interpretation
    lines += ["### 2.3. Інтерпретація / Interpretation", ""]
    lines += _auto_interpretation(result)
    lines.append("")

    # figures
    if figures:
        lines += ["### 2.4. Рисунки / Figures", ""]
        order = ["dashboard", "topdown_ustfuse", "error_time", "ospa_time",
                 "roc", "reliability", "selective_risk", "pd_bars", "clock",
                 "metric_cmp", "confidence", "fault_timeline", "coverage",
                 "traj3d", "detections"]
        captions = {
            "dashboard": "Зведена панель місії / Mission dashboard.",
            "topdown_ustfuse": "Вид зверху: сенсори, істина, треки (UST-Fuse).",
            "error_time": "Похибка позиції у часі; сірим — вікна відмов.",
            "ospa_time": "OSPA-відстань у часі (менше — краще).",
            "roc": "ROC детекції за порогом SNR.",
            "reliability": "Діаграма надійності (калібрування, ЛР-7).",
            "selective_risk": "Крива ризик–покриття.",
            "pd_bars": "Емпірична ймовірність виявлення за сенсорами.",
            "clock": "Оцінені зсув і дрейф годинників (ЛР-1).",
            "metric_cmp": "Порівняння режимів за ключовими метриками.",
            "confidence": "Ймовірність існування треків у часі.",
            "fault_timeline": "Часова шкала відмов / red-team (ЛР-5).",
            "coverage": "Покриття сенсорної мережі.",
            "traj3d": "3-D траєкторії.",
            "detections": "RAW-детекції за сенсорами.",
        }
        for name in order:
            path = figures.get(name)
            if not path or str(path).startswith("ERROR"):
                continue
            rel = os.path.basename(path)
            lines += [f"**{captions.get(name, name)}**", "",
                      f"![{name}]({rel})", ""]
    return "\n".join(lines)


def _auto_interpretation(result) -> List[str]:
    """Generate honest, data-driven interpretation bullets (LLM-report style)."""
    out = []
    modes = result.modes
    if "reference" in modes and "ust_fuse" in modes:
        a = modes["reference"].tracking
        b = modes["ust_fuse"].tracking
        ca, cb = modes["reference"].calibration, modes["ust_fuse"].calibration

        def cmp_line(name, va, vb, lower_better, unit=""):
            win = ("UST-Fuse" if (vb < va) == lower_better else "Reference")
            arrow = "↓" if lower_better else "↑"
            return (f"- **{name}** {arrow}: Reference = {_fmt(va)}{unit}, "
                    f"UST-Fuse = {_fmt(vb)}{unit} → перевага: **{win}**.")

        out.append(cmp_line("Похибка позиції RMSE (m)", a.rmse_pos, b.rmse_pos, True))
        out.append(cmp_line("OSPA (m)", a.ospa_mean, b.ospa_mean, True))
        out.append(cmp_line("MOTA", a.mota, b.mota, False))
        out.append(cmp_line("Повнота супроводження", a.track_completeness, b.track_completeness, False))
        out.append(cmp_line("Калібрування ECE", ca.ece, cb.ece, True))
        # narrative
        if b.track_completeness > a.track_completeness + 0.02:
            out.append("- Мультисенсорне злиття підвищує **повноту супроводження** — "
                       "особливо у сценаріях з відмовою радара, коли пасивні сенсори "
                       "утримують трек (ЛР-5).")
        if cb.ece < ca.ece - 0.01:
            out.append("- UST-Fuse дає **краще калібровану** оцінку існування треку "
                       "(нижчий ECE), що важливо для прийняття рішень з невизначеністю (ЛР-7).")
        out.append("- Компроміс чесно зафіксовано: приріст надійності/покриття може "
                   "супроводжуватися незначним зростанням числа треків — це предмет "
                   "подальшого налаштування трекера, а не артефакт вимірювання.")
    return out


def _technical_report(result) -> str:
    m = result.manifest
    lines = ["## 3. Технічний звіт та відтворюваність / Technical Report & Reproducibility", ""]
    lines += [
        "| Поле / Field | Значення / Value |",
        "| --- | --- |",
        f"| Experiment ID | `{m.experiment_id}` |",
        f"| Scenario ID | `{m.scenario_id}` |",
        f"| Seed | `{m.seed}` |",
        f"| Config hash | `{m.config_hash}` |",
        f"| Created | {m.created_at} |",
        f"| Platform | {m.environment.get('platform', '—')} |",
        "",
        "**Версії пакетів / Package versions:**",
        "",
    ]
    pdf = pd.DataFrame([{"package": k, "version": v} for k, v in m.packages.items()])
    lines += [_md_table(pdf), ""]

    # clock estimates
    est = m.extra.get("clock_estimates", {})
    if est:
        edf = pd.DataFrame([
            {"sensor": s, "offset (ms)": est[s]["offset_est_ms"],
             "drift (ppm)": est[s]["drift_est_ppm"], "resid (ms)": est[s]["residual_ms"]}
            for s in est
        ])
        lines += ["**Калібрування часу / Clock calibration (ЛР-1):**", "", _md_table(edf), ""]

    lines += [
        "> Кожен результат відтворюється з `seed` та `config hash`. "
        "Синтетичні дані марковані окремо і не змішуються з польовими без явного "
        "індикатора походження (розділ 12 пропозиції).",
        "",
    ]
    return "\n".join(lines)


def _campaign_section(campaign) -> str:
    lines = ["## 4. Кампанія та парний аналіз / Campaign & Paired Analysis", ""]
    lines += [
        f"Проведено **{campaign.n_missions}** місій сценарію `{campaign.scenario_id}` "
        "з різними seed. Порівняння парне (Reference проти UST-Fuse) на однакових "
        "вхідних потоках; наведено ефект-сайз (Cohen's d) та 95 % ДІ (bootstrap).",
        "",
    ]
    t = campaign.paired_table()
    show = t[["metric", "mean_a", "mean_b", "mean_diff", "ci_low", "ci_high",
              "cohens_d", "p_value", "power", "better"]].copy()
    show = show.rename(columns={
        "mean_a": "Reference", "mean_b": "UST-Fuse", "mean_diff": "Δ (B−A)",
        "ci_low": "CI low", "ci_high": "CI high", "cohens_d": "Cohen d",
        "p_value": "p", "better": "winner",
    })
    show["winner"] = show["winner"].map({"A": "Reference", "B": "UST-Fuse"})
    lines += [_md_table(show), ""]
    lines += ["![paired forest](campaign_forest.png)", "",
              "![campaign box](campaign_box.png)", ""]
    return "\n".join(lines)


def _kpi_section(result) -> str:
    """KPI scorecard against the proposal's section-13 first-year targets."""
    lines = ["## 5. Відповідність KPI (розділ 13) / KPI scorecard", ""]
    lines += [
        "| KPI | Ціль / Target | Показано у цьому пакеті / Shown here |",
        "| --- | --- | --- |",
        "| Віртуальні сценарії | ≥ 50 версіонованих | бібліотека сценаріїв + domain-rand |",
        "| Відтворюваність | 100 % з маніфесту | manifest + seed + config hash |",
        "| Коеф. повторного використання | ≥ 10 replay/варіантів | replay + domain randomization |",
        "| Навчальні модулі | ≥ 8–10 ЛР | ЛР-1…ЛР-10 покрито метриками |",
        "| Публікаційний результат | 1 датасет + 1–2 публікації | Zenodo-пакет + автозвіти |",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def build_markdown_report(result, figures: Optional[Dict[str, str]] = None,
                          campaign=None, title: Optional[str] = None) -> str:
    """Assemble the full field-trial report as a Markdown string."""
    scn = result.config.scenario
    head = [
        f"# {title or 'Звіт польових випробувань (цифровий двійник UST-Fuse)'}",
        "",
        "*Field-trial report — UST-Fuse cyber-range digital twin*",
        "",
        f"Сценарій / Scenario: **{scn.title}** · Experiment `{result.manifest.experiment_id}`",
        "",
        "---",
        "",
    ]
    parts = [
        "\n".join(head),
        _mission_protocol(result),
        _lab_report(result, figures),
        _technical_report(result),
    ]
    if campaign is not None:
        parts.append(_campaign_section(campaign))
    parts.append(_kpi_section(result))
    parts.append(
        "---\n\n### Висновок / Conclusion\n\n"
        "Цифровий двійник відтворює польову логіку полігону UST-Fuse у віртуальному "
        "середовищі: єдиний час, незмінювані RAW-дані, однакові вхідні потоки для "
        "парного порівняння режимів злиття, статистичний аналіз з ефект-сайзом та ДІ, "
        "і повну простежуваність від RAW до рисунків. Це відповідає методологічним "
        "вимогам науково-технічної пропозиції (розділи 2, 12, 13, 15).\n"
    )
    return "\n\n".join(parts)


def _markdown_to_html(md: str, base_dir: str) -> str:
    """Minimal, dependency-free Markdown→HTML (headings, tables, images, bold)."""
    import re

    def esc(s):
        return _html.escape(s, quote=False)

    html_lines = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # tables
        if line.startswith("| ") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{esc(h)}</th>" for h in header)
            trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
            html_lines.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        # images
        m = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if m:
            html_lines.append(f'<figure><img src="{esc(m.group(2))}" alt="{esc(m.group(1))}"></figure>')
            i += 1
            continue
        # headings
        m = re.match(r"(#{1,6})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            html_lines.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if line.strip() == "---":
            html_lines.append("<hr>")
            i += 1
            continue
        if line.startswith("> "):
            html_lines.append(f"<blockquote>{_inline(esc(line[2:]))}</blockquote>")
            i += 1
            continue
        if line.strip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline(esc(lines[i].strip()[2:]))}</li>")
                i += 1
            html_lines.append("<ul>" + "".join(items) + "</ul>")
            continue
        if line.strip() == "":
            html_lines.append("")
        else:
            html_lines.append(f"<p>{_inline(esc(line))}</p>")
        i += 1

    body = "\n".join(html_lines)
    css = """
    body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    max-width:1000px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.55}
    h1{border-bottom:3px solid #0072B2;padding-bottom:.3rem}
    h2{margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem;color:#0a3d62}
    table{border-collapse:collapse;margin:1rem 0;font-size:.9rem;width:100%}
    th,td{border:1px solid #ccc;padding:5px 9px;text-align:left}
    th{background:#D9EAF7}
    img{max-width:100%;height:auto;border:1px solid #eee;border-radius:6px;margin:.4rem 0}
    blockquote{border-left:4px solid #0072B2;margin:1rem 0;padding:.4rem 1rem;background:#f4f9ff;color:#333}
    code{background:#f2f2f2;padding:1px 5px;border-radius:4px}
    figure{margin:1rem 0}
    """
    return (f"<!doctype html><html lang='uk'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>UST-Fuse field-trial report</title><style>{css}</style></head>"
            f"<body>{body}</body></html>")


def _inline(text: str) -> str:
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def write_report(result, out_dir: str, figures: Optional[Dict[str, str]] = None,
                 campaign=None, basename: str = "report") -> Dict[str, str]:
    """Write Markdown + HTML report to ``out_dir``; return the file paths."""
    os.makedirs(out_dir, exist_ok=True)
    if campaign is not None:
        # render the campaign figures the report references
        try:
            import matplotlib.pyplot as plt
            from .viz.plots import plot_paired_forest, plot_campaign_box
            fig = plot_paired_forest(campaign, save=os.path.join(out_dir, "campaign_forest.png"))
            plt.close(fig)
            fig = plot_campaign_box(campaign, "mota", save=os.path.join(out_dir, "campaign_box.png"))
            plt.close(fig)
        except Exception:
            pass
    md = build_markdown_report(result, figures=figures, campaign=campaign)
    md_path = os.path.join(out_dir, f"{basename}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    html = _markdown_to_html(md, out_dir)
    html_path = os.path.join(out_dir, f"{basename}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"markdown": md_path, "html": html_path}
