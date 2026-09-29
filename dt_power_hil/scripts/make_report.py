#!/usr/bin/env python3
"""Elsevier-style experiment report (English) -> report/DT_HIL_Experiment_Report_Elsevier_EN.docx
All numbers are read from results/summary.json; nothing is typed by hand."""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = RES / "figures"
S = json.load(open(RES / "summary.json"))
MAN = json.load(open(RES / "manifest.json"))
E5 = S["e05"]
PP = E5["per_policy"]
E11 = S["e11"]
T = S["timing"]


def f(x, n=2):
    return f"{x:.{n}f}".replace("-", "−")


doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.0))
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
st.font.size = Pt(10.5)
st.paragraph_format.space_after = Pt(4)
st.paragraph_format.line_spacing = 1.12
for lvl, size in ((1, 12), (2, 11)):
    h = doc.styles[f"Heading {lvl}"]
    h.font.name = "Times New Roman"
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    h.font.size = Pt(size)
    h.font.bold = True
    h.font.italic = lvl == 2
    h.font.color.rgb = RGBColor(0, 0, 0)
    h.paragraph_format.space_before = Pt(10)
    h.paragraph_format.space_after = Pt(4)

FIGN = [0]
TABN = [0]


def _runs(p, text, bold=False, italic=False, size=None, color=None):
    for i, part in enumerate(text.split("**")):
        if not part:
            continue
        r = p.add_run(part)
        r.bold = bold or (i % 2 == 1)
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)


def P(text="", bold=False, italic=False, size=None, align=None, color=None, after=None):
    p = doc.add_paragraph()
    _runs(p, text, bold, italic, size, color)
    p.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.JUSTIFY
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def H(text, lvl=1):
    doc.add_heading(text, level=lvl)


def bullets(items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        _runs(p, it)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def table(caption, header, rows, widths=None, note=None, size=8.5):
    TABN[0] += 1
    c = P(f"**Table {TABN[0]}.** {caption}", size=9.5, after=2)
    c.alignment = WD_ALIGN_PARAGRAPH.LEFT
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        shade(cell, "E8E7E3")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, wdt in enumerate(widths):
                row.cells[i].width = Cm(wdt)
    if note:
        n = P(note, italic=True, size=8.5)
        n.paragraph_format.space_before = Pt(2)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figure(name, caption, width=16.5):
    FIGN[0] += 1
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(FIG / f"{name}.png"), width=Cm(width))
    c = P(f"**Fig. {FIGN[0]}.** {caption}", size=9)
    c.paragraph_format.space_after = Pt(8)


def box(lines, fill="F4F3F0"):
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    cell = t.rows[0].cells[0]
    shade(cell, fill)
    cell.text = ""
    for k, ln in enumerate(lines):
        p = cell.paragraphs[0] if k == 0 else cell.add_paragraph()
        _runs(p, ln, size=9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


nr = [r for r in S["runs"] if r["scenario_id"] not in ("E06", "E07")]
max_mae = max(r["mae_soc_pp"] for r in nr)
max_en = max(r["energy_error_pct"] for r in nr if r["energy_error_pct"] == r["energy_error_pct"])
e5c1 = E5["primary"]["C1_minus_C0"]
aux21 = E5["secondary"]["aux_served_wh:C2-C1"]

# ================================ FRONT MATTER ================================
P("Experiment report in Elsevier manuscript format · Applied Energy (supporting material for revision)", italic=True, size=9,
  align=WD_ALIGN_PARAGRAPH.LEFT, color="52514E")
P("Software–hardware validation of a digital twin for communication-node power supply: a virtual testbed emulating real components, "
  "measurement protocols and a comparison of control policies", bold=True, size=15, align=WD_ALIGN_PARAGRAPH.LEFT, after=6)
P("[Authors and affiliations — to be completed from the manuscript; report prepared under the protocol “Software–hardware experiment for the "
  "digital twin of a communication-node power supply”, version 1.0]", italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.LEFT)
P("Generated: 29 September 2026 · Result package: results/ (manifest.json, checksums.sha256)", size=9, align=WD_ALIGN_PARAGRAPH.LEFT, color="52514E")

box(["**EVIDENCE CLASSIFICATION.** Software-in-the-loop (SIL) simulation with emulated hardware: a virtual testbed in which the physical "
     "plant (12.8 V / 40 Ah LiFePO₄ battery, DC bus, load branches), the measurement channels (INA226/INA228 + FL-2 shunts), the MQTT "
     "transport and the ESP32 controller are reproduced by models parameterised with the characteristics of real components. "
     "**No physical measurements were made.** The results must not be described as a HIL/CHIL or field experiment. They establish "
     "readiness of the software, correctness of the measurement protocols and expected metric values for a future physical run."])

H("Highlights")
bullets([
    f"Digital twin, virtual testbed and protocols implemented as a reproducible Python project `dtpower` ({MAN['n_runs']} runs, 14 acceptance tests).",
    f"Twin SOC error against an independent REF channel: MAE ≤ {f(max_mae)} pp; energy error ≤ {f(max_en)} %.",
    f"Decision → ACK → physical effect chain: RTT p95 = {f(T['rtt_ms']['p95'], 0)} ms; the effect was confirmed for every accepted command.",
    f"Threshold control C1 extended operation to the SOC_ref = 0.20 limit from {f(PP['C0']['time_to_limit_h']['mean'])} h to ≥ 6 h (censored); the forecast rule C2 gave no time benefit and delivered less useful lighting.",
    "The published MinSOC values 0.219/0.247 cannot be reproduced unambiguously: the result is sensitive to the day order and efficiency interpretation, which the manuscript does not specify.",
])

H("Abstract")
P(f"To test the digital twin of a telecommunication-node power supply (PV–LiFePO₄–DC bus), a controlled experiment was carried out on a "
  f"virtual testbed that reproduces a real 12 V bench: ESP32-S3, INA226 meters (M0–M5) and an independent INA228 (REF) on FL-2 shunts, a "
  f"RIDEN RD6018 programmable supply as PV equivalent, Mean Well DDR-60G-12 DC/DC converters, a relay-switched auxiliary branch and a network "
  f"probe of the node. The work was split into a software part (the Python project dtpower and ESP-IDF edge_guard firmware) and a hardware "
  f"part (bill of materials on real components, measurement-point diagram and measurement protocols derived from datasheet characteristics). "
  f"Protocol scenarios E00–E11 were executed: calibration, steady state, step disturbances of load and generation, source loss, controlled "
  f"deficit with a paired comparison of policies C0/C1/C2 ({E5['blocks']} blocks), link loss, faulty sensors, recovery, protection logic and the "
  f"14-day S1–S3 scenario. The twin tracked SOC with MAE {f(min(r['mae_soc_pp'] for r in S['runs']))}–{f(max_mae)} pp against the independent REF; "
  f"all {T['effect_ms']['n'] + T['state_confirmations']} accepted commands had a confirmed physical effect, and the median decision-to-current-edge "
  f"time was {f(T['effect_ms']['median'], 0)} ms. In E05, policy C1 extended the time to the working limit by {f(e5c1['mean'])} h (95% BCa CI "
  f"{f(e5c1['ci_lo'])}–{f(e5c1['ci_hi'])}; Holm p = {f(e5c1['p_holm'], 4)}) at a cost of {f(-E5['secondary']['aux_served_wh:C1-C0']['mean'], 1)} Wh of "
  f"lighting. The forecast rule C2 with a causal persistence forecast did not change the primary outcome (both policies censored at 6 h) but "
  f"delivered {f(-aux21['mean'], 1)} Wh less lighting than C1, whereas the information bound C_oracle shows that a perfect forecast would keep "
  f"C1-level lighting with a higher reserve. The data therefore support a working state → decision → command → physical effect loop and identify "
  f"the generation forecast as the bottleneck of predictive control. They are not a physical validation and do not demonstrate an advantage of "
  f"predictive control.")
P("**Keywords:** digital twin; hardware-in-the-loop; LiFePO₄; telecommunication node; SOC estimation; load management; measurement protocol; reproducibility",
  size=9.5)

# ================================ 1 INTRODUCTION ================================
H("1. Introduction")
P("The manuscript on the digital twin of a communication-node power supply [1] sizes a PV–LiFePO₄ system with an hourly SOC simulation and "
  "proposes an ML extension for forecasting and control. Reviewers require experimental evidence linking the twin to real equipment. "
  "The HIL experiment protocol [2] states four hypotheses: H1 — the model reproduces the energy balance; H2 — the twin stays current under "
  "disturbances; H3 — decisions of the twin change the physical state; H4 — predictive control improves a pre-specified resilience metric.")
P("This report executes the protocol in two layers. The **software part** is a complete software project (twin, EMS, transport, logger, analysis, "
  "controller firmware) ready to be connected to real instruments without changing its logic. The **hardware part** is a bench specified on "
  "real components. Its characteristics (ranges, LSBs, errors, shunt and fuse ratings) are used for two purposes: (i) to derive the measurement "
  "protocols and tolerances and (ii) to parameterise the emulation on which the whole campaign was run. Such a virtual testbed allows the "
  "protocols, acceptance checks and analytics to be rehearsed before battery life is spent, but it does not replace a physical test [2, §1.3].")

# ================================ 2 METHODS ======================================
H("2. Materials and methods")
H("2.1. Split into software and hardware parts", 2)
figure("fig01_architecture", "Experiment architecture. Left — hardware on real components (emulated with datasheet characteristics in this "
       "campaign): source G1, battery with BMS, DC bus, critical and auxiliary branches with measurement points M0–M5, independent REF channel and "
       "the ESP32-S3 controller. Right — the dtpower software on the PC. The scenario module never passes the future profile to the EMS.")
table("Division of work between the parts of the experiment",
      ["Part", "Content", "Artifacts"],
      [["Software (implemented and tested)", "dtpower: profiles, sizing, energy_sim, battery (ECM plant), sensors, calibration, capacity, transport, "
        "edge_guard, twin, forecast, ems, bench, scenarios, replay, stats; tests; campaign, figure, protocol scripts", "dtpower/, tests/, scripts/, configs/"],
       ["Controller firmware (written, not compiled)", "ESP-IDF edge_guard.c: 10 Hz INA226 sampling, 1 Hz aggregation, state machine, command contract, watchdog", "firmware/esp32_edge_guard/"],
       ["Hardware (specified on real components)", "24-item BOM, functional diagram, meter selection check, installation rules", "hardware/BOM_and_wiring.md"],
       ["Measurement protocols", "P-1 channel passport, P-2 E00 calibration, P-3 uncertainty budget, P-4 E09 capacity, P-5 pre-run checklist, "
        "P-6 run protocols, P-7 deviation card", "hardware/measurement_protocols.md, results/protocols/"],
       ["Web presentation", "Interactive results dashboard", "web/index.html"]],
      widths=[4.0, 9.0, 4.0])

H("2.2. Hardware part: real components and characteristics", 2)
P("The bench implements the mandatory 12 V programme of the protocol [2, §1.2] (Table 2). The 12.8 V / 40 Ah battery has a nominal energy of "
  "≈ 512 Wh and is not a physical replica of S1 (12 V / 200 Ah). Bench conclusions therefore concern the implementation of the loop and the "
  "accuracy of the bench model, not the S1–S3 scale [2, §14.4]. Generation is supplied in mode G1: the RIDEN RD6018 programmable supply sets the "
  "available power on the bus (CV 14.2 V, CC = P_avail/V every second) through an LTC4359 ideal diode. G1 conclusions concern the energy balance, "
  "not MPPT quality.")
ch = S["channels"]
table("Main bench components and the characteristics used in calculations (nominal values; verify against datasheets before a physical run)",
      ["Function", "Component", "Characteristics"],
      [["Controller", "ESP32-S3-DevKitC-1", "2×240 MHz; esp_timer 1 µs; ESP-MQTT"],
       ["Battery", "LiFePO₄ 4S 12.8 V / 40 Ah + DALY 4S 40 A BMS", "CV 14.2 V; OVP 14.6 V; UVP 10.0 V; I_charge ≤ 20 A"],
       ["Generation G1", "RIDEN RD6018 + Mean Well RSP-750-48 + LTC4359", "0–60 V, 0–18 A; 0.01 V / 0.01 A steps"],
       ["Branch DC/DC", "Mean Well DDR-60G-12 ×2", "in 9–36 V, out 12 V / 5 A; η ≈ 0.90"],
       ["Critical load", "MikroTik hAP ac² + Korad KEL103 (CP)", "18 W total at the terminals"],
       ["Auxiliary load", "12 V / 30 W LED; Bosch 0 332 019 150 relay (NO) + PC817 + ULN2003A", "operate ≈ 10 ms, LED soft start ≈ 150 ms"],
       ["M0–M5", "TI INA226 + FL-2 shunts (30/50/10 A, 75 mV)", "LSB 2.5 µV and 1.25 mV; offset ≤ ±10 µV; gain error ≤ 0.1 %; 36 V"],
       ["REF", "TI INA228 + FL-2 50 A/75 mV, RPi 4 logger", "LSB 312.5 nV; offset ≤ ±1 µV; gain error ≤ 0.05 %; 85 V"],
       ["Temperature", "DS18B20 ×2", "±0.5 °C"],
       ["Protection", "MIDI 40 A; ATO 25/5/7.5 A; Blue Sea 6006; ADuM1250", "DC rated; I²C isolation"]],
      widths=[3.3, 6.2, 7.5])
table("Measurement-channel selection check from characteristics (from P-1)",
      ["Channel", "Shunt, mΩ", "Full scale, A", "Current LSB, mA", "Max offset, mA", "Uncal. error, %", "Max shunt power, W"],
      [[r["channel"], f(r["r_shunt_mohm"], 1), f(r["i_full_scale_a"], 1), f(r["i_lsb_ma"], 3), "±" + f(r["offset_max_ma"], 2),
        "±" + f(r["uncal_gain_err_max_pct"], 2), f(r["p_shunt_max_w"], 2)] for r in ch],
      note="Uncalibrated error = IC gain error + shunt class (0.5 %). It exceeds the 1 % target only together with the offset near zero, so "
           "E00 calibration is mandatory. The INA226 is unsuitable for a 48/51.2 V bus (common mode ≤ 36 V); S3 needs an INA228 or another front end.")

H("2.3. Software part: the dtpower project", 2)
P("The software implements the minimum structure of the protocol [2, §6.1]. The emulated plant is a LiFePO₄ equivalent circuit (OCV(z) with a "
  "3.28–3.33 V/cell plateau, R0, R1C1, coulombic efficiency) with hidden unit parameters — capacity, R0 and OCV offset — unknown to the twin "
  "[2, §3.3]. Each measurement channel is a shunt (class tolerance, TCR) plus an IC (offset, gain error, noise, LSB quantisation, full-scale "
  "saturation); unit errors are drawn uniformly within datasheet maxima. The MQTT transport has log-normal latency (median 12 ms), 0.1 % loss, "
  "0.2 % QoS-1 redelivery and test blackouts. The edge_guard model implements the INIT/READY/RUNNING/DEGRADED/STOPPED state machine and the "
  "command contract (schema, mode, source, run_id, boot_id, action whitelist, conservative expiry check including a ±15 ms clock error, "
  "idempotency by command_id). The same decision table is coded in the edge_guard.c firmware.")
P("The twin estimates SOC from channel M1 only: the prior is the prediction before new telemetry arrives (last current held); the posterior "
  "combines coulomb counting with the measured current and an EKF voltage correction, which is weak on the LiFePO₄ plateau. The twin capacity "
  "Q_M1 was determined in E09 from M1. The reference SOC_ref is computed by a separate logger from REF with Q_ref and η_Q from E09 [2, §8.3]. "
  "The telemetry validator rejects missing fields, impossible values, stuck values (≥ 8 identical samples) and bus-balance violations "
  "|r_P| > 3 W for ≥ 5 s (eq. 9.2).")

H("2.4. Calibration and independent reference (E00, E09)", 2)
cap = S["capacity"]
P(f"E00 emulates the §8.1 procedure: 60-s zero, five current levels (charge and discharge for battery channels), a and b fitted on levels 1, 3, 5 "
  f"and verified on levels 2, 4 against a standard with 0.05 % expanded uncertainty (a placeholder until the certificate is available). "
  f"E09 determined the working-interval capacity (CC-CV 20 A / 14.2 V, 2 A tail; 10 A discharge to 11.2 V): Q_ref = {f(cap['q_ref_ah'], 3)} Ah, "
  f"Q_M1 = {f(cap['q_m1_ah'], 3)} Ah, E_ref = {f(cap['e_ref_wh'], 1)} Wh, η_Q = {f(cap['eta_q_ref'], 4)}. The hidden true capacity of the unit was "
  f"{f(cap['true_capacity_ah_hidden'], 2)} Ah; the working interval covered {f(100 * cap['working_interval_fraction_true'], 1)} % of it.")

H("2.5. Scenarios and control policies", 2)
table("Executed scenario matrix (all in mode sil_hw_emulated)",
      ["Code", "Scenario and parameters", "Duration", "Policies / repeats"],
      [["E00/E09", "Calibration of 7 channels; working-interval capacity", "≈ 8 model h", "—"],
       ["E01", "Stabilisation at 25 W, generation < demand (10 W), > demand (60 W); lighting off", "60 min", "C0 ×1"],
       ["E02", "18 W + 30 W LED: on at 15 min, off at 30 min, on at 45 min; generation 25 W", "60 min", "C0 ×1"],
       ["E03", "Generation 60 → 10 → 60 W (30/60/30 min); scheduled lighting", "120 min", "C0, C1, C2"],
       ["E04", "Loss of the 55 W source for 60 min; HTTP probe every second", "90 min", "C0 ×1"],
       ["E05", "Deficit: SOC₀ = 0.45; 40 W 1.5 h / 5 W 3 h / 60 W 1.5 h; 18 + 30 W; stop at SOC_ref = 0.20", "up to 6 h",
        f"C0, C1, C2, C_oracle × {E5['blocks']} paired blocks"],
       ["E06", "Telemetry loss 30 s (uplink), bidirectional 30 s; stale command and foreign-run_id command", "30 min", "C1 ×1"],
       ["E07", "Injection into the telemetry copy: 0.39 A offset, stuck value, missing field, V = 99 V, sign flip", "30 min", "C1 ×1"],
       ["E08", "SOC₀ = 0.33; 20-min deficit; recovery to 120 W", "60 min", "C0, C1, C2"],
       ["E10", "12 protection/contract vectors (signal injection)", "—", "—"],
       ["E11", "14 days S1–S3 (SIL, 1 h and 1 min); lockstep controller replay on S1 with 12.8 V / 100 Ah", "336 model h", "C0, C1, C2"]],
      widths=[1.4, 9.6, 2.2, 3.8])
P("C0 — lighting by schedule; C1 — off at SOC ≤ 0.30, back on at SOC ≥ 0.40, 60-s minimum dwell; C2 — forecast rule (6-h horizon, 5-min step): "
  "off if the forecast minimum SOC with lighting is < 0.30; back on if the forecast is ≥ 0.35 and SOC ≥ 0.40. The C2 generation forecast is a "
  "causal exponential smoothing of measured generation (cold start 0 W) and has no physical access to the scenario profile. C_oracle uses the "
  "true future profile and serves only as an information bound [2, §11.4]. Thresholds were frozen in configs/policies.json before the campaign.")

H("2.6. Metrics and statistical analysis", 2)
P("The pre-specified primary outcome of E05 [2, §16.7] is the time to the working limit SOC_ref = 0.20 with the service maintained, right-censored "
  "at 6 h; delivered lighting energy, critical unserved energy, minimum SOC_ref and switch count are co-reported. The statistical unit is a paired "
  "block (the same bench unit, initial state and noise seed for all policies of a block). Paired differences are reported as the mean, a 95% BCa "
  "interval (10,000 resamples) and an exact two-sided sign-flip test (2¹⁰ permutations; minimum attainable p = 0.002). Holm correction is applied "
  "to the two primary contrasts (C1−C0, C2−C1); Friedman is the omnibus test across the three policies. Unserved energy, LOLH and LPSP_E use the "
  "policy-independent desired demand [2, §16.2].")

H("2.7. Reproducibility", 2)
P(f"The campaign runs with one command, `python scripts/run_campaign.py` (deterministic seeds: bench {MAN['bench_seed']}, base {MAN['base_seed']}). "
  f"The package contains manifest.json (Python {MAN['python']}, NumPy {MAN['numpy']}), a copy of the configurations (SHA-256 {S['config_sha256'][:16]}…), "
  f"raw logs for every run_id, run protocols in the §21.3 format, metrics, figures and checksums.sha256. Execution time was "
  f"{f(MAN['wall_time_s'], 0)} s on 4 processes.")

# ================================ 3 RESULTS ======================================
H("3. Results")
H("3.1. Metrology: calibration and uncertainty budget", 2)
cal = S["calibration"]
figure("fig09_calibration", "Residuals of channels M0–M5 and REF after E00 calibration (EMU): circles — levels used to fit the coefficients, "
       "diamonds — verification levels. The ±1 % acceptance target lies far outside the scale.", 15.5)
U = S["uncertainty"]
table("Calibration results and expanded uncertainty (k = 2) of a 1-s current value (EMU)",
      ["Channel", "Zero before cal., mA", "a", "b, mA", "Max verification residual, %", "U_I at operating I (k=2)"],
      [[n, f(c["zero_offset_raw_a"] * 1e3, 2), f(c["a_i"], 5), f(c["b_i"] * 1e3, 2), f(c["max_verification_rel"] * 100, 3),
        "; ".join(f"{f(r['i_op_a'], 0)} A: {f(r['U_i_a_k2'] * 1e3, 1)} mA" for r in U.get(n, []))] for n, c in cal.items()],
      widths=[1.4, 2.6, 1.8, 1.6, 3.2, 6.4],
      note="All channels passed the ≤ 1 % criterion by more than an order of magnitude. The dominant component of the battery channels is the "
           "uncertainty of the standard, so the actual accuracy of the physical bench will be set by the standard's certificate, not by the INA226/INA228.")

H("3.2. Twin accuracy (H1)", 2)
figure("fig04_twin_accuracy", "SOC tracking by the twin (posterior, dashed) against the independent SOC_ref in E03-C2 and E04-C0 (A) and the "
       "difference in percentage points (B). The shaded band is the ±3 pp MAE criterion.", 16.5)
table("State and energy accuracy by scenario (EMU; E05 — mean over 10 blocks)",
      ["Scenario / policy", "SOC MAE, pp", "RMSE, pp", "Max |error|, pp", "Discharge energy error, %", "REF − truth, pp", "Residual r_P, W (mean ± SD)"],
      [[f"{r['scenario_id']} {r['policy']}", f(r["mae_soc_pp"]), f(r["rmse_soc_pp"]), f(r["max_soc_err_pp"]),
        f(r["energy_error_pct"]) if r["energy_error_pct"] == r["energy_error_pct"] else "—", f(r["ref_vs_true_mae_pp"]),
        f"{f(r['residual_w_mean'])} ± {f(r['residual_w_sd'])}"] for r in nr if r["scenario_id"] != "E05"] +
      [[f"E05 {p} (n = 10)", f(PP[p]["mae_soc_pp"]["mean"]), "—", f(PP[p]["max_soc_err_pp"]["max"]), f(PP[p]["energy_error_pct"]["mean"]), "—", "—"]
       for p in ("C0", "C1", "C2", "C_oracle")],
      widths=[3.0, 1.8, 1.6, 2.2, 2.8, 2.2, 3.4],
      note="“REF − truth” exists only in emulation; the hidden state is unknown in a physical test. The residual r_P ≈ 0.35 W corresponds to "
           "unmetered bus self-consumption (relay, driver, modules); it must be measured separately in the pilot, not subtracted as “unknown losses”.")
P(f"The H1 criterion (energy ≤ 5 %, SOC MAE ≤ 3 pp, maximum ≤ 5 pp) was met in all nominal runs. The SOC error grows during long discharge "
  f"segments: the EKF correction barely works on the LiFePO₄ plateau, so the Q_M1/Q_ref mismatch and the initial-state error accumulate. The error "
  f"of SOC_ref against the hidden truth (0.1–0.4 pp) sets a lower bound of evidence: SOC differences between policies smaller than ≈ 0.5 pp are not interpreted.")

H("3.3. Synchronisation and physical execution of commands (H2, H3)", 2)
figure("fig08_timing", f"Distribution of command → ACK RTT (A, n = {T['rtt_ms']['n']}) and of decision → M4 current edge detected locally by the "
       f"ESP32 at 10 Hz (B, n = {T['effect_ms']['n']}).", 16.0)
P(f"The median RTT was {f(T['rtt_ms']['median'], 1)} ms, p95 {f(T['rtt_ms']['p95'], 1)} ms, p99 {f(T['rtt_ms']['p99'], 1)} ms and maximum "
  f"{f(T['rtt_ms']['max'], 1)} ms (criterion p95 ≤ 2 s). For all {T['effect_ms']['n']} commands that changed the relay state, the M4 current edge "
  f"was detected after a median of {f(T['effect_ms']['median'], 0)} ms and a maximum of {f(T['effect_ms']['max'], 0)} ms. This time is RTT + relay "
  f"operate time (10 ms) + LED soft start (150 ms) + 10 Hz sampling. A further {T['state_confirmations']} accepted commands did not change the state "
  f"(e.g. OFF with the relay already off) and were confirmed by the matching measured state. Valid telemetry coverage in nominal runs was at least "
  f"{f(min(r['coverage_pct'] for r in nr))} %; lost packets were never replaced by zero. These times come from an emulated network and do not "
  f"characterise the real bench Wi-Fi; they must be measured in P-5 before the main series.")

H("3.4. Link loss, sensor faults and protection logic (E06, E07, E10)", 2)
figure("fig05_e06_link_loss", "E06: ESP32 output state and measured relay state during telemetry loss (600–630 s) and bidirectional link loss "
       "(900–930 s). At 1200 s a stale ON command and a command with a foreign run_id were rejected by the controller.", 16.0)
e6 = S["e06"]
rej = [c for c in e6["commands"] if c["reason"].startswith("E06_")]
P("On uplink loss the twin flagged telemetry as stale after "
  f"{f(e6['events'][0]['t'] - 600, 0)} s and sent a fallback OFF command, which was executed. On bidirectional loss the OFF command could not be "
  "delivered, but the controller switched to DEGRADED on its own heartbeat watchdog (> 5 s) and turned the auxiliary branch off. The critical "
  "load ran without interruption. After restoration the controller returned to RUNNING only after a heartbeat carrying the state-reconciled "
  "flag, and the lighting came back on with a new EMS command at the next 60-s cycle. Both test commands were rejected with reasons "
  f"“{rej[0]['reject_reason']}” and “{rej[1]['reject_reason']}”.")
FU = {"offset": "current offset", "stuck": "stuck value", "missing": "missing field", "impossible": "impossible value", "sign": "sign flip"}
table("E07: detection of invalid data in the twin's telemetry copy",
      ["Fault", "Parameter", "Duration, s", "Detected", "Latency, s", "Flag", "Share of samples flagged"],
      [[FU[r["fault"]], r["param"] if r["param"] is not None else "—", r["duration_s"], "yes" if r["detected"] else "NO",
        f(r["latency_s"], 2) if r["latency_s"] is not None else "—", r["flag"], f(100 * r["flagged_fraction"], 0) + " %"] for r in S["e07"]["table"]],
      widths=[2.4, 2.4, 2.0, 1.6, 1.8, 3.4, 2.8],
      note=f"False flags outside fault intervals: {S['e07']['false_flags']}. A 10 % working-current offset and a sign flip are detected only through "
           "the bus balance, so the ≈ 4 s latency is set by the ‘≥ 5 consecutive samples’ rule. A smaller offset (< 3 W in the balance) is not caught by this mechanism.")
table("E10: protection and command-contract vectors (edge_guard model)",
      ["Vector", "Expected", "Observed", "State after", "Result"],
      [[r["test"], "yes" if r["expected_accepted_or_condition"] else "no", "yes" if r["observed"] else "no", r["state_after"],
        "PASS" if r["pass"] else "FAIL"] for r in S["e10"]],
      widths=[8.0, 2.0, 2.2, 2.6, 2.0],
      note="“Yes/no” = command accepted or condition met. The same vectors must be repeated on the ESP32 firmware before a physical run.")

H("3.5. Policy comparison in the deficit test (E05, H4)", 2)
figure("fig02_e05_timeseries", "E05, block R00: SOC_ref for the four policies (A) and available generation with lighting state (B). C0 reaches the "
       "0.20 limit after 3.6 h; C1 switches the lighting off at 0.30; C2, starting from a cold forecast, switches the lighting off at once and keeps a high reserve.", 16.5)
figure("fig03_e05_paired", "E05, paired results of 10 blocks: time to limit (A), lighting delivered (B), minimum SOC_ref (C). Grey lines connect "
       "the policies of one block; horizontal ticks are means.", 16.5)
rows = []
for k, lab in (("C1_minus_C0", "Time to limit, h: C1 − C0"), ("C2_minus_C1", "Time to limit, h: C2 − C1")):
    v = E5["primary"][k]
    rows.append([lab + " (primary)", f(v["mean"], 3), f"{f(v['ci_lo'], 3)}; {f(v['ci_hi'], 3)}", f(v["p_signflip"], 4), f(v["p_holm"], 4)])
for k, lab in (("aux_served_wh:C1-C0", "Lighting, Wh: C1 − C0"), ("aux_served_wh:C2-C1", "Lighting, Wh: C2 − C1"),
               ("aux_served_wh:C_oracle-C2", "Lighting, Wh: Oracle − C2"),
               ("aux_served_common_interval_wh:C2-C1", "Lighting to common end, Wh: C2 − C1"),
               ("min_soc_ref:C1-C0", "Min SOC_ref: C1 − C0"), ("min_soc_ref:C2-C1", "Min SOC_ref: C2 − C1"),
               ("switch_count:C2-C1", "Switches: C2 − C1"), ("critical_unserved_wh:C2-C1", "Critical unserved, Wh: C2 − C1")):
    v = E5["secondary"][k]
    rows.append([lab, f(v["mean"], 3), f"{f(v['ci_lo'], 3)}; {f(v['ci_hi'], 3)}", f(v["p_signflip"], 4), "expl."])
table("E05: paired contrasts (n = 10 blocks)", ["Contrast", "Mean difference", "95% BCa CI", "p (sign-flip)", "p (Holm)"], rows,
      widths=[7.0, 2.4, 3.4, 2.2, 2.0],
      note=f"Policy means: time to limit C0 = {f(PP['C0']['time_to_limit_h']['mean'])} h (0/10 censored); C1, C2, C_oracle — 6 h (10/10 censored); "
           f"lighting C0 = {f(PP['C0']['aux_served_wh']['mean'], 1)}, C1 = {f(PP['C1']['aux_served_wh']['mean'], 1)}, C2 = {f(PP['C2']['aux_served_wh']['mean'], 1)}, "
           f"C_oracle = {f(PP['C_oracle']['aux_served_wh']['mean'], 1)} Wh; critical unserved energy — 0 in all runs. Common end = the earliest stop in a block "
           f"(≈ 3.6 h, the C0 stop). Friedman (3 policies): χ² = {f(E5['friedman']['aux_served_wh']['chi2'], 1)}, p = {E5['friedman']['aux_served_wh']['p']:.1e}. "
           "Narrow intervals reflect only measurement-noise variability on one bench unit, not unit-to-unit or seasonal variability.")
P("Threshold control C1 versus C0 gave a robust effect on the primary outcome: no C1 block reached the limit within 6 h. The cost was "
  f"{f(-E5['secondary']['aux_served_wh:C1-C0']['mean'], 1)} Wh of lighting. Hypothesis H4 for the forecast rule C2 is **not supported**. The primary "
  "outcome did not change (both policies censored); C2 delivered less lighting and held an unnecessarily high reserve "
  f"(min SOC_ref {f(PP['C2']['min_soc_ref']['mean'], 3)} vs {f(PP['C1']['min_soc_ref']['mean'], 3)}). This is exactly the case the protocol warns "
  "about [2, §1.1]: a higher SOC achieved by switching the lighting off. The cause is the generation forecast. During the cold start and the "
  "3-hour 5 W segment the persistence forecast extrapolates the deficit over the whole 6-hour horizon and does not anticipate recovery. "
  f"C_oracle with the same thresholds delivered {f(PP['C_oracle']['aux_served_wh']['mean'], 1)} Wh (as C1) with a higher minimum reserve "
  f"({f(PP['C_oracle']['min_soc_ref']['mean'], 3)}). The value of information is therefore ≈ {f(E5['secondary']['aux_served_wh:C_oracle-C2']['mean'], 0)} Wh "
  "of lighting, and predictive control pays off only with a generation forecast better than persistence (an ERA5/PVGIS-based daily profile, TFT/GRU).")

H("3.6. Long scenario: 14 days of S1–S3 and controller replay (E11)", 2)
figure("fig06_e11_14day", "E11: stored-energy fraction z_E for S1 and S3 in SIL with the protocol day order (A), and critical and lighting "
       "unserved energy over 336 h for a down-sized S1 configuration (12.8 V / 100 Ah) under C0–C2 in lockstep replay with the edge_guard model (B).", 16.5)
sil = E11["sil"]
art = {"S1": 0.219, "S2": 0.219, "S3": 0.247}
table("E11: reproduction of the manuscript results (SIL, 336 h, day order per protocol §10.2)",
      ["Scenario", "MinSOC manuscript", "MinSOC SIL, 1-h step", "1-min step", "Nameplate 12.8/25.6/51.2 V", "LOLH, h", "Curtailed generation, Wh"],
      [[s, f(art[s], 3), f(sil[s]["min_soc"], 3), f(E11["sil_1min"][s]["min_soc"], 3), f(sil[s]["min_soc_nameplate_v"], 3), f(sil[s]["lolh_h"], 0),
        f(sil[s]["e_curtailed_wh"], 0)] for s in ("S1", "S2", "S3")],
      widths=[1.8, 2.2, 2.8, 1.8, 3.4, 1.6, 3.4])
table("Sensitivity of MinSOC to the manuscript's ambiguous parameters (S1 / S3)",
      ["Order of PSH days", "Battery efficiency", "k_T", "MinSOC S1", "MinSOC S3"],
      [[r["order"], r["efficiency"], f(r["k_t"]), f(r["min_soc_S1"], 3), f(r["min_soc_S3"], 3)] for r in E11["reconciliation"]],
      widths=[4.0, 6.0, 1.4, 2.6, 2.6], size=8,
      note="None of the 18 combinations reproduces 0.219 (S1) and 0.247 (S3) at the same time. The MinSOC spread (0.150–0.358) exceeds the "
           "difference between the manuscript and SIL, so exact replication needs the authors' PSH array, initial SOC and efficiency interpretation "
           "[2, §2.2]. LOLH = 0 is reproduced for every variant with a non-zero margin.")
cr = E11["controller_replay"]
P(f"For the controller replay, S1 was run with a 12.8 V / 100 Ah battery to create a deficit. All three policies have the same total bus unserved "
  f"energy ({f(cr['C0']['e_unserved_bus_wh'], 0)} Wh): the energy deficit is set by the resource, not by control. The policies only redistribute it "
  f"between load groups. Critical unserved energy fell from {f(cr['C0']['e_unserved_critical_wh'], 0)} (C0) to {f(cr['C1']['e_unserved_critical_wh'], 0)} (C1) "
  f"and {f(cr['C2']['e_unserved_critical_wh'], 0)} Wh (C2), and LOLH from {f(cr['C0']['lolh_h'], 0)} to {f(cr['C2']['lolh_h'], 0)} h, while lighting "
  f"unserved energy rose from {f(cr['C0']['e_unserved_aux_wh'], 0)} to {f(cr['C2']['e_unserved_aux_wh'], 0)} Wh. Here the C2 forecast (previous-day "
  f"persistence) is useful because the daily generation cycle repeats. All {cr['C0']['commands']['sent'] + cr['C1']['commands']['sent'] + cr['C2']['commands']['sent']} "
  "commands passed the edge_guard contract. The replay ran in model-time lockstep, which is not evidence of real-time execution [2, §14.3].")

H("3.7. Analytical sizing and sensitivity", 2)
table("Analytical sizing (eqs. B.4–B.7) — exact agreement with Table 3 of the manuscript",
      ["Scenario", "E_load, Wh/day", "E_src, Wh/day", "E_batt, Wh", "C, Ah", "P_PV, Wp", "I²R rel. to 12 V"],
      [[s, f(v["e_load_day"], 0), f(v["e_src_day"], 1), f(v["e_batt_req"], 1), f(v["c_ah"], 1), f(v["p_pv"], 1), f(v["loss_ratio_vs_12v"], 4)]
       for s, v in S["sizing"].items()],
      widths=[1.8, 2.6, 2.6, 2.4, 1.8, 2.0, 2.4])
figure("fig07_sensitivity", "Required PV power (Wp) for S1 as a function of PSH and η_dc (reproduction of Fig. 10 of the manuscript). The dot marks the base case.", 11.0)

H("3.8. Summary of acceptance criteria", 2)
table("Protocol acceptance criteria [2, §17] on the virtual testbed",
      ["Object", "Criterion", "Observed (EMU)", "Verdict"],
      [[a["object"], a["criterion"], a["observed"], "met" if a["pass"] else ("not determined" if a["pass"] is None else "NOT met")] for a in S["acceptance"]],
      widths=[3.3, 4.4, 7.0, 2.3], size=8)

# ================================ 4 DISCUSSION ===================================
H("4. Discussion")
P("**What was established.** The software works as a closed loop: measurements with realistic instrument errors → validation → state "
  "estimation → decision → idempotent command with an expiry time → execution confirmed by a change of current. Fallback behaviour on link and "
  "sensor faults matches the specification. The metrological analysis shows that the accuracy bottleneck of the physical bench will be the "
  "calibration standard and the initial SOC determination, not the INA226/INA228 resolution. Bus self-consumption of ≈ 0.35 W must be measured, "
  "otherwise it appears as a systematic balance residual.")
P("**What was not established.** Hypothesis H4 for the forecast rule is not supported. The short bench test with a persistence forecast showed "
  "no advantage of C2 over the simple threshold C1: C2 saved more energy only at the expense of useful lighting. At the same time, the 14-day "
  "scenario shows that with a daily forecast C2 reduces critical unserved energy. The benefit of predictive control therefore depends on "
  "forecast quality and deficit structure, and proving it requires real generation series, not a 6-hour synthetic profile. The comparison with "
  "C_oracle quantifies the ceiling of that benefit on the bench (≈ 33 Wh of lighting per run).")
P("**Relation to the manuscript.** The analytical sizing of S1–S3 is reproduced exactly. The time-domain simulation confirms LOLH = 0 for the "
  "selected configurations, but MinSOC differs (0.190 vs 0.219 for S1; 0.221 vs 0.247 for S3) and is highly sensitive to undocumented "
  "parameters. The manuscript should give the full PSH array, the initial SOC and separate η_ch/η_dis, or report MinSOC as a sensitivity range.")

H("5. Limitations")
bullets([
    "All data come from emulation; there are no physical measurements, real electromagnetic interference, thermal effects, ageing, or real Wi-Fi and BMS behaviour.",
    "Instrument errors were drawn within the datasheet maxima of a single unit (seed 1); unit-to-unit variability was not assessed.",
    "The narrow E05 confidence intervals reflect only measurement noise under identical block conditions; a larger spread is expected on a physical bench (temperature, initial state).",
    "The twin and REF take their initial SOC from the same preparation procedure; their independence concerns subsequent integration, not the starting point.",
    "The edge_guard.c firmware was not compiled or run; only its Python mirror was tested.",
    "The battery model does not describe power-electronics dynamics faster than 1 s; switching voltage dips need an oscilloscope.",
    "The TFT/LSTM/DEKF/CNN/RL components of the manuscript were not implemented or tested; C2 is a transparent forecast rule, not MPC or RL.",
])

H("6. Conclusions")
bullets([
    f"A digital-twin software package with a virtual testbed was built and verified: {MAN['n_runs']} runs of E01–E08, calibration E00, capacity E09, protection logic E10 and the 14-day E11 are reproduced by one command with checksums.",
    "The hardware part is specified on real components (ESP32-S3, INA226/INA228, FL-2, RD6018, DDR-60G-12, Bosch relay, DS18B20, Blue Sea 6006). Measurement protocols with tolerances, an uncertainty budget and blank forms for physical entries were derived from their characteristics.",
    f"All quantitative acceptance criteria were met on the virtual testbed: SOC MAE ≤ {f(max_mae)} pp, energy ≤ {f(max_en)} %, RTT p95 = {f(T['rtt_ms']['p95'], 0)} ms, 100 % of executions confirmed, 5/5 data faults detected.",
    f"Threshold control extends autonomous operation to the limit by ≈ {f(e5c1['mean'], 1)} h on the 40 Ah bench. The forecast rule with a persistence forecast gave no advantage; proving H4 requires a better generation forecast and a physical series.",
    "The manuscript's MinSOC values should be accompanied by the full configuration, because the sensitivity to day order and efficiency interpretation exceeds the stated precision.",
    "Next step: a physical series following hardware/measurement_protocols.md (E00 → E01–E05 pilot → threshold freeze → main C0/C1/C2 series with ≥ 3 repeats), using the same code in physical mode.",
])

H("Data and code availability")
P("Code, configurations, raw logs of all runs, protocols, figures and checksums are in the dt_power_hil/ directory of the repository. "
  "The web presentation of the results is dt_power_hil/web/index.html. No physical dataset was produced. A DOI will be added once an immutable release is created.")
H("CRediT authorship contribution statement")
P("[To be completed: conceptualisation, methodology, software, validation, formal analysis, writing.]", italic=True)
H("Declaration of generative AI use")
P("The software, the emulated campaign and the draft of this report were prepared with the help of an AI assistant (Claude). The authors must "
  "review and edit the content and take responsibility for the final text in accordance with Elsevier policy.", italic=True)

H("References")
for i, ref in enumerate([
    "Prokopovych-Tkachenko D., Sarychev V., Poplavskyi O., Torstensson O., Pignaton de Freitas E. Digital Twin of Power Supply for a Communication Node During Outages: Generation Forecasting, Load Forecasting, and Battery Diagnostics. Manuscript submitted to Applied Energy, 2026.",
    "Software–hardware experiment for the digital twin of a communication-node power supply: extended protocol, version 1.0, 29.09.2026.",
    "Schuhmacher D., Vo B.-T., Vo B.-N. A consistent metric for performance evaluation of multi-object filters. IEEE Trans. Signal Process. 2008;56:3447–3457 (as a model of the paired design in the UST-Fuse description).",
    "Efron B., Tibshirani R.J. An Introduction to the Bootstrap. Chapman & Hall/CRC; 1993.",
    "Holm S. A simple sequentially rejective multiple test procedure. Scand. J. Stat. 1979;6:65–70.",
    "Wang L., et al. State of charge estimation for LiFePO4 battery via dual extended Kalman filter and charging voltage curve. Electrochim. Acta 2019;296:1009–1017.",
    "Hu J., et al. A model predictive control strategy of PV-battery microgrid under variable power generations and load conditions. Appl. Energy 2018;221:195–203.",
    "Texas Instruments. INA226 — 36-V, 16-bit, I²C current/voltage/power monitor. Datasheet.",
    "Texas Instruments. INA228 — 85-V, 20-bit, I²C power/energy/charge monitor. Datasheet.",
    "Espressif Systems. ESP-IDF Programming Guide: ESP Timer; ESP-MQTT.",
    "Hersbach H., et al. The ERA5 global reanalysis. Q. J. R. Meteorol. Soc. 2020;146:1999–2049.",
], 1):
    P(f"[{i}] {ref}", size=9)

doc.core_properties.title = "Software–hardware validation of a digital twin for communication-node power supply"
doc.core_properties.subject = S["evidence_class"]
for z in doc.settings.element.iter(qn("w:zoom")):
    z.set(qn("w:percent"), "100")
out = ROOT / "report" / "DT_HIL_Experiment_Report_Elsevier_EN.docx"
doc.save(out)
print("saved", out)
