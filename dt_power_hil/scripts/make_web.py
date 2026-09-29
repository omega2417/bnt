#!/usr/bin/env python3
"""Build web/index.html (self-contained dashboard) from results/*.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
S = json.load(open(RES / "summary.json"))
SER = json.load(open(RES / "series_selected.json"))
MAN = json.load(open(RES / "manifest.json"))


def ds(s, keys, step=6):
    return {k: [None if v is None else round(v, 4) for v in s[k][::step]] for k in keys}


e05 = {p: ds(SER[f"20260929_E05_{p}_R00_EMU"], ["t", "soc_ref", "soc_post", "relay", "p_gen_avail"]) for p in ("C0", "C1", "C2", "C_oracle")}
twin = {rid.split("_")[1] + " " + rid.split("_")[2]: ds(SER[rid], ["t", "soc_ref", "soc_post", "soc_true"], 3)
        for rid in ("20260929_E03_C2_R00_EMU", "20260929_E04_C0_R00_EMU", "20260929_E02_C0_R00_EMU", "20260929_E08_C1_R00_EMU")}
e11 = {"S1": [round(x, 4) for x in S["e11"]["sil"]["S1"]["soc"]], "S3": [round(x, 4) for x in S["e11"]["sil"]["S3"]["soc"]],
       "S1_100Ah_C0": [round(x, 4) for x in S["e11"]["controller_replay"]["C0"]["soc"]],
       "S1_100Ah_C2": [round(x, 4) for x in S["e11"]["controller_replay"]["C2"]["soc"]],
       "replay": {p: {k: S["e11"]["controller_replay"][p][k] for k in ("e_unserved_critical_wh", "e_unserved_aux_wh", "e_unserved_bus_wh", "lolh_h", "switches")}
                  for p in ("C0", "C1", "C2")},
       "sil": {s: {"min_soc": S["e11"]["sil"][s]["min_soc"], "min_soc_1min": S["e11"]["sil_1min"][s]["min_soc"],
                   "min_soc_nameplate": S["e11"]["sil"][s]["min_soc_nameplate_v"], "lolh": S["e11"]["sil"][s]["lolh_h"]} for s in ("S1", "S2", "S3")},
       "recon": S["e11"]["reconciliation"]}
runs = [{k: r[k] for k in ("run_id", "scenario_id", "policy", "repeat", "duration_h", "stop_reason", "coverage_pct", "mae_soc_pp", "max_soc_err_pp",
                           "energy_error_pct", "aux_served_wh", "critical_unserved_wh", "min_soc_ref", "switch_count", "availability_pct")} |
        {"rtt_p95": r["rtt"].get("p95_ms")} for r in S["runs"]]
data = {"acceptance": S["acceptance"], "e05": {"series": e05, "primary": {k: {x: v[x] for x in ("mean", "ci_lo", "ci_hi", "p_signflip", "p_holm", "diffs")} for k, v in S["e05"]["primary"].items()},
                                               "secondary": {k: {x: v[x] for x in ("mean", "ci_lo", "ci_hi", "p_signflip")} for k, v in S["e05"]["secondary"].items()},
                                               "per_policy": S["e05"]["per_policy"], "blocks": S["e05"]["blocks"]},
        "twin": twin, "e11": e11, "timing": S["timing"], "e07": S["e07"], "e10": S["e10"], "calibration": S["calibration"],
        "channels": S["channels"], "capacity": S["capacity"], "sizing": S["sizing"], "runs": runs,
        "manifest": {k: MAN[k] for k in ("n_runs", "python", "numpy", "config_sha256", "wall_time_s", "evidence_class")}}
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
for tpl, name in (("template.html", "index.html"), ("template_ua.html", "index_UA.html")):
    out = (ROOT / "web" / tpl).read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    (ROOT / "web" / name).write_text(out, encoding="utf-8")
    print(f"web/{name}", len(out) // 1024, "KB")
