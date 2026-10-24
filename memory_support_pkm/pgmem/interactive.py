"""Interactive figures (Plotly) for the notebook and HTML reports.

Every figure has hover details; colours match ``plots`` so an entity looks
the same in static and interactive views.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from .plots import COND_COLORS, COND_LABELS, COND_ORDER, DX_COLORS, DX_LABELS, DX_ORDER, RADAR_AXES

FONT = dict(family="Inter, Helvetica, Arial, sans-serif", size=12, color="#0b0b0b")
LAYOUT = dict(template="plotly_white", font=FONT, paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
              margin=dict(l=40, r=30, t=70, b=40), hoverlabel=dict(font_size=12))


def _rgba(hex_: str, a: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def save(fig: go.Figure, out: Path | None, name: str) -> go.Figure:
    if out is not None:
        fig.write_html(Path(out) / name, include_plotlyjs="cdn")
    return fig


def episode_sankey(ep: pd.DataFrame, out: Path | None = None) -> go.Figure:
    """Condition -> what really happened -> what was recorded. The flow
    'not completed/completed -> missed (inferred)' is where silence becomes a
    fabricated outcome (I3); the proposed framework routes it to 'unknown'."""
    d = ep.copy()
    d["truth"] = np.where(~d.completed_true, "Not completed",
                          np.where(d.completion_level.fillna(0) <= 1, "Completed at L0–L1", "Completed at L2–L4"))
    rec_labels = {"completed": "Recorded: completed (with source)", "unknown": "Recorded: unknown",
                  "postponed": "Recorded: postponed", "declined": "Recorded: declined",
                  "missed_inferred": "Recorded: missed (inferred from silence)"}
    d["rec"] = d.recorded_state.map(rec_labels)
    nodes = [COND_LABELS[c] for c in COND_ORDER] + ["Completed at L0–L1", "Completed at L2–L4", "Not completed"] \
        + list(rec_labels.values())
    idx = {n: i for i, n in enumerate(nodes)}
    node_col = [COND_COLORS[c] for c in COND_ORDER] + ["#123f78", "#eda100", "#8a8984"] + \
               ["#1baf7a", "#c3c2b7", "#9cc2ee", "#9cc2ee", "#e34948"]
    src, tgt, val, col, hov = [], [], [], [], []
    for (c, t), n in d.groupby(["condition", "truth"]).size().items():
        src.append(idx[COND_LABELS[c]]); tgt.append(idx[t]); val.append(n)
        col.append(_rgba(COND_COLORS[c], 0.35)); hov.append(f"{COND_LABELS[c]} → {t}: {n:,} episodes")
    for (c, t, r), n in d.groupby(["condition", "truth", "rec"]).size().items():
        src.append(idx[t]); tgt.append(idx[r]); val.append(n)
        bad = "missed" in r and t != "Not completed"
        col.append("rgba(227,73,72,0.75)" if bad else _rgba(COND_COLORS[c], 0.3))
        hov.append(f"{COND_LABELS[c]}: {t} → {r}: {n:,}" + ("  ⚠ completed task logged as missed (I3)" if bad else ""))
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nodes, color=node_col, pad=18, thickness=16, line=dict(color="#fcfcfb", width=2)),
        link=dict(source=src, target=tgt, value=val, color=col, customdata=hov,
                  hovertemplate="%{customdata}<extra></extra>"),
    ))
    fig.update_layout(**LAYOUT, height=560,
                      title="Episode flow: condition → true outcome → recorded state "
                            "<br><sup>red ribbons = completed tasks recorded as missed (violates I3)</sup>")
    return save(fig, out, "sankey_episodes.html")


def recall_sunburst(rc: pd.DataFrame, out: Path | None = None) -> go.Figure:
    """Condition -> stratum -> decision, coloured by whether the decision
    matches the reference behaviour."""
    d = rc.copy()
    d["condition_label"] = d.condition.map(COND_LABELS)
    d["verdict"] = np.where(d.appropriate, "appropriate", "inappropriate")
    g = d.groupby(["condition_label", "stratum", "decision", "verdict"]).size().reset_index(name="n")
    fig = px.sunburst(g, path=["condition_label", "stratum", "decision"], values="n", color="verdict",
                      color_discrete_map={"appropriate": "#2a78d6", "inappropriate": "#e34948", "(?)": "#c3c2b7"})
    fig.update_traces(hovertemplate="%{id}<br>%{value:,} answers<extra></extra>", insidetextorientation="radial")
    fig.update_layout(**LAYOUT, height=640,
                      title="Recall decisions by condition and stratum<br><sup>blue = reference behaviour, "
                            "red = not; click a ring to zoom</sup>")
    return save(fig, out, "sunburst_recall.html")


def condition_radar(summary: pd.DataFrame, out: Path | None = None) -> go.Figure:
    fig = go.Figure()
    labels = [lbl.replace("\n", " ") for _, lbl, _ in RADAR_AXES]
    for c in COND_ORDER:
        r, txt = [], []
        for m, lbl, f in RADAR_AXES:
            row = summary[m].loc[c]
            ok = not pd.isna(row.estimate)
            r.append(f(row.estimate) if ok else 0)
            txt.append(f"{m} = {row.estimate:.3f} [{row.ci_low:.3f}, {row.ci_high:.3f}]" if ok else f"{m}: undefined")
        fig.add_trace(go.Scatterpolar(r=r + r[:1], theta=labels + labels[:1], name=COND_LABELS[c], fill="toself",
                                      line=dict(color=COND_COLORS[c], width=2), fillcolor=_rgba(COND_COLORS[c], .15),
                                      customdata=txt + txt[:1], hovertemplate="%{customdata}<extra>%{fullData.name}"
                                                                              "</extra>"))
    fig.update_layout(**LAYOUT, height=560, polar=dict(radialaxis=dict(range=[0, 1.02], tickfont_size=9)),
                      title="Condition profiles — outer ring is better (hover for raw value and 95% CI)")
    return save(fig, out, "radar_conditions.html")


def cohort_parallel(cohort: pd.DataFrame, pm: pd.DataFrame, out: Path | None = None) -> go.Figure:
    """Parallel coordinates: every line is one synthetic person, coloured by
    TSR under the proposed framework. Drag on an axis to filter (brush)."""
    p = pm[pm.condition == "proposed"][["participant_id", "TSR", "independence", "coverage"]]
    d = cohort.merge(p, on="participant_id")
    dx_code = d.diagnosis.map({k: i for i, k in enumerate(DX_ORDER)})
    dims = [dict(label="Diagnosis", values=dx_code, tickvals=[0, 1, 2], ticktext=[DX_LABELS[x] for x in DX_ORDER]),
            dict(label="Age", values=d.age), dict(label="MoCA", values=d.moca),
            dict(label="PRMQ-P", values=d.prmq_prospective), dict(label="Digital literacy", values=d.digital_literacy),
            dict(label="Lives alone", values=d.lives_alone.astype(int), tickvals=[0, 1], ticktext=["no", "yes"]),
            dict(label="Independence", values=d.independence, range=[0, 1]),
            dict(label="Coverage", values=d.coverage, range=[0, 1]),
            dict(label="TSR", values=d.TSR)]
    fig = go.Figure(go.Parcoords(line=dict(color=d.TSR, colorscale=[[0, "#e34948"], [0.5, "#e9e8e4"], [1, "#2a78d6"]],
                                           showscale=True, colorbar=dict(title="TSR")), dimensions=dims))
    fig.update_layout(**LAYOUT, height=520, title="Who benefits least? Metadata → outcome per participant "
                                                  "(drag along any axis to filter)")
    return save(fig, out, "parallel_cohort.html")


def weekly_trajectories(ep: pd.DataFrame, cohort: pd.DataFrame, out: Path | None = None) -> go.Figure:
    """Animated bubble chart: each bubble is a participant, x = MoCA,
    y = cumulative TSR up to that week, size = escalations so far."""
    d = ep.merge(cohort[["participant_id", "moca", "diagnosis"]], on="participant_id")
    d["week"] = d.day // 7 + 1
    g = d.groupby(["condition", "participant_id", "week"]).agg(
        done=("completed_true", "sum"), n=("episode_id", "size"), esc=("escalations", "sum"),
        moca=("moca", "first"), diagnosis=("diagnosis", "first")).reset_index()
    g = g.sort_values("week")
    for k in ("done", "n", "esc"):
        g[k] = g.groupby(["condition", "participant_id"])[k].cumsum()
    g["TSR"] = g.done / g.n
    g["Condition"] = g.condition.map(COND_LABELS)
    g["MoCA (jittered)"] = g.moca + np.random.default_rng(0).uniform(-.35, .35, len(g))
    g["Week"] = "week " + g.week.astype(str)
    fig = px.scatter(g, x="MoCA (jittered)", y="TSR", size="esc", color="Condition", animation_frame="Week",
                     animation_group="participant_id", hover_name="participant_id",
                     hover_data=dict(diagnosis=True, esc=True, moca=True, **{"MoCA (jittered)": False}),
                     color_discrete_map={COND_LABELS[c]: COND_COLORS[c] for c in COND_ORDER},
                     size_max=18, range_y=[0.3, 1.02], range_x=[8, 31], opacity=0.65)
    fig.update_layout(**LAYOUT, height=560,
                      title="Cumulative task success per participant, week by week (press ▶)<br>"
                            "<sup>bubble size = escalations so far</sup>")
    return save(fig, out, "animated_weeks.html")


def risk_coverage(curve: pd.DataFrame, theta_low: float, out: Path | None = None) -> go.Figure:
    c = curve.dropna()
    fig = go.Figure(go.Scatter(x=c.coverage, y=c.F_ext, mode="lines+markers",
                               marker=dict(color=c.theta_low, colorscale="Blues", size=7, showscale=True,
                                           colorbar=dict(title="θ_low")),
                               line=dict(color="#2a78d6", width=2), customdata=c[["theta_low", "released"]],
                               hovertemplate="θ_low=%{customdata[0]:.2f}<br>coverage=%{x:.3f}<br>F_ext=%{y:.3f}"
                                             "<br>released=%{customdata[1]}<extra></extra>"))
    pt = curve.loc[(curve.theta_low - theta_low).abs().idxmin()]
    fig.add_trace(go.Scatter(x=[pt.coverage], y=[pt.F_ext], mode="markers", name="current θ_low",
                             marker=dict(size=16, symbol="circle-open", color="#0b0b0b", line_width=2)))
    fig.update_layout(**LAYOUT, height=440, showlegend=False, xaxis_title="Answer coverage C",
                      yaxis_title="Recall faithfulness F_ext", title="Risk–coverage of the release rule (Eq. 5)")
    return save(fig, out, "risk_coverage.html")
