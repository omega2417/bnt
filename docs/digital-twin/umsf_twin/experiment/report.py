"""Report generator following the Appendix F template of the specification.

The report is written from the artifacts of a finished run, so every number it
contains is traceable to a file whose SHA-256 is in the manifest, and the claim
boundary is emitted automatically rather than left to the author's memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["render_markdown", "write_report"]

CLAIM_BOUNDARY = (
    "Ці результати характеризують поведінку програмної моделі за заданих припущень. "
    "Вони не є вимірюваннями реальної мережі УМСФ і не підтверджують фактичний час "
    "перемикання WAN/VPN/АВР, Wi-Fi-покриття, автономність джерел живлення або "
    "польову точність детекторів."
)


def _table(rows: list[tuple[str, Any]]) -> str:
    lines = ["| Показник | Значення |", "|---|---|"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return "\n".join(lines)


def render_markdown(summary: dict[str, Any], manifest: dict[str, Any] | None = None) -> str:
    aggregate = summary.get("aggregate", {})
    network = aggregate.get("network", {})
    power = aggregate.get("power", {})
    detection = aggregate.get("detection", {})
    gates = summary.get("gates", {})

    parts = [
        f"# Звіт синтетичного експерименту `{summary.get('run_id')}`",
        "",
        "## F.1. Ідентифікація",
        _table([
            ("experiment_id", summary.get("experiment_id")),
            ("run_id", summary.get("run_id")),
            ("mode", summary.get("mode")),
            ("evidence_class", summary.get("evidence_class")),
            ("replicates", summary.get("replicates")),
            ("duration_s", summary.get("duration_s")),
            ("config_hash", summary.get("config_hash")),
            ("engine_source_hash",
             (manifest or {}).get("hashes", {}).get("engine_source", "n/a")),
        ]),
        "",
        "## F.3. Мережеві результати",
    ]
    for site_id, row in network.items():
        parts += [f"### {site_id}", _table(list(row.items())), ""]

    parts += ["## F.4. Енергетичні результати", _table(list(power.items())), "",
              "## F.5. Виявлення", _table([(k, v) for k, v in detection.items()
                                           if not isinstance(v, dict)]), ""]

    parts += ["## F.6. Data quality gates",
              "| Gate | Результат | Значення | Поріг |", "|---|---|---|---|"]
    for result in gates.get("results", []):
        parts.append(f"| {result['gate']} | "
                     f"{'PASS' if result['passed'] else 'FAIL'} | "
                     f"{result['value']} | {result['threshold']} |")

    parts += ["", "## F.9. Межа твердження", CLAIM_BOUNDARY, ""]
    if summary.get("invariant_notes"):
        parts += ["## Відхилення від документованої інвентаризації",
                  *[f"- {note}" for note in summary["invariant_notes"]], ""]
    return "\n".join(parts)


def write_report(run_dir: str | Path, filename: str = "report.md") -> Path:
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) \
        if manifest_path.exists() else None
    target = run_dir / filename
    target.write_text(render_markdown(summary, manifest), encoding="utf-8")
    return target
