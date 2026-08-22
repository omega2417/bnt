"""Narrative report generated from the analysis outputs.

The report is written by code, not by hand: every sentence that contains
a number pulls it from the run-level summary or the effect table, so the
text cannot drift away from the data.  The hypothesis verdicts follow
pre-registered decision rules stated in :func:`hypothesis_verdicts`.

When the dataset is not ``MEASURED`` the report opens with an explicit
banner and the results section is labelled accordingly, so the file can
never be mistaken for the outcome of a real campaign.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from .config import (
    BASELINE_CONFIG,
    CONFIG_BLOCK_MS,
    DATA_REQUIRED_FIELDS,
    N_CLIENTS,
    POLL_S,
    THRESHOLDS,
    TOPOLOGY_LABELS,
    get_profile,
)
from .tables import tex_escape, to_markdown

BANNER_EN = (
    "> **Provenance: {prov}.** These numbers come from the reference model in "
    "`alp.simulate`, executed with the pre-registered protocol. They demonstrate "
    "that the analysis pipeline is complete and reproducible. They are **not** "
    "measurements of the cyber range and must not be reported as experimental "
    "results. Section *Outstanding data* lists what a real campaign has to supply."
)

BANNER_UK = (
    "> **Походження даних: {prov}.** Наведені числа отримано з еталонної моделі "
    "`alp.simulate`, виконаної за попередньо зареєстрованим протоколом. Вони "
    "підтверджують повноту й відтворюваність аналітичного конвеєра. Це **не** "
    "вимірювання кіберполігона, і їх не можна подавати як результати експерименту. "
    "Розділ *Відсутні дані* перелічує те, що має надати реальна кампанія."
)


def _cfg(config: str) -> str:
    ms = CONFIG_BLOCK_MS.get(config)
    return f"{config} (stock)" if ms is None else f"{config} ({ms} ms)"


def hypothesis_verdicts(
    summary: pd.DataFrame, effects: pd.DataFrame, cells: pd.DataFrame
) -> pd.DataFrame:
    """Evaluate H1-H3 against pre-registered decision rules.

    H1  Shorter target pacing lowers the block-wait component: the median
        observed block interval must fall monotonically with the target.
    H2  The gain is non-linear and shrinks as queueing grows.  Measured as
        *realisation efficiency*: the observed p99 improvement of the
        fastest profile over the 1000 ms profile, divided by the improvement
        that the block-wait model of section 8.2 predicts, namely
        ``0.99 * (1000 - B_fastest)`` ms.  The comparison is restricted to
        strata where the 1000 ms reference itself stays stable, so the
        statistic measures diminishing returns and not the collapse of an
        overloaded baseline.  H2 holds when efficiency at the highest such
        load is below efficiency at the lowest.
    H3  The fastest profile need not own the tail: in at least one stratum
        another profile's mean p99 is lower than or equal to that of the
        fastest profile.
    """
    fastest = min(
        (c for c in summary.config.unique() if CONFIG_BLOCK_MS.get(c)),
        key=lambda c: CONFIG_BLOCK_MS[c],
    )
    rows: List[Dict[str, object]] = []

    intervals = (
        summary[summary.config != BASELINE_CONFIG]
        .groupby("config").observed_block_interval_ms.median()
        .sort_index()
    )
    targets = pd.Series({c: CONFIG_BLOCK_MS[c] for c in intervals.index})
    ordered = intervals.reindex(targets.sort_values().index)
    h1 = bool(np.all(np.diff(ordered.to_numpy()) >= -1e-9))
    rows.append(
        {
            "hypothesis": "H1",
            "statement": "shorter target pacing lowers the block-wait component",
            "rule": "median observed block interval is monotone in the target",
            "evidence": "; ".join(
                f"{c}: {v:.0f} ms" for c, v in ordered.items()
            ),
            "supported": h1,
        }
    )

    lo, hi = summary.load_tps.min(), summary.load_tps.max()
    reference = min(
        (c for c in summary.config.unique() if CONFIG_BLOCK_MS.get(c)),
        key=lambda c: -CONFIG_BLOCK_MS[c],
    )
    predicted = 0.99 * (CONFIG_BLOCK_MS[reference] - CONFIG_BLOCK_MS[fastest])
    stable_loads = sorted(
        cells[(cells.config == reference) & cells.stable_all].load_tps.unique()
    )
    mean_p99 = summary.groupby(["config", "load_tps"]).p99_ms.mean()
    efficiency = {}
    for load in stable_loads:
        try:
            gain = mean_p99.loc[(reference, load)] - mean_p99.loc[(fastest, load)]
        except KeyError:
            continue
        efficiency[load] = 100.0 * gain / predicted
    if len(efficiency) >= 2:
        first, last = min(efficiency), max(efficiency)
        h2 = efficiency[last] < efficiency[first]
        evidence = (
            f"realisation efficiency {efficiency[first]:.0f} % at {first} tx/s vs "
            f"{efficiency[last]:.0f} % at {last} tx/s "
            f"(predicted gain {predicted:.0f} ms from {reference} to {fastest})"
        )
    else:
        h2, evidence = False, (
            f"{reference} is stable at fewer than two loads; the rule cannot be "
            "evaluated on this dataset"
        )
    rows.append(
        {
            "hypothesis": "H2",
            "statement": "the gain is non-linear and shrinks as queueing grows",
            "rule": f"realisation efficiency of {fastest} vs {reference} falls with "
                    f"load, over loads where {reference} stays stable",
            "evidence": evidence,
            "supported": bool(h2),
        }
    )

    by_cell = summary.groupby(["topology", "load_tps", "config"]).p99_ms.mean()
    beaten = []
    for (topology, load), group in by_cell.groupby(level=[0, 1]):
        flat = group.droplevel([0, 1])
        if fastest not in flat.index:
            continue
        rivals = flat.drop(index=[fastest])
        rivals = rivals[rivals <= flat[fastest] + 1e-9]
        beaten.extend(
            f"{TOPOLOGY_LABELS.get(topology, topology)} @ {load} tx/s: "
            f"{c} {v:.0f} ms vs {fastest} {flat[fastest]:.0f} ms"
            for c, v in rivals.items()
        )
    rows.append(
        {
            "hypothesis": "H3",
            "statement": f"{fastest} need not own the tail",
            "rule": f"another profile matches or beats {fastest} on mean p99 in at "
                    "least one stratum",
            "evidence": "; ".join(beaten[:4]) + (
                f" (and {len(beaten) - 4} further strata)" if len(beaten) > 4 else ""
            ) if beaten else f"{fastest} kept the lowest p99 in every stratum",
            "supported": bool(beaten),
        }
    )
    return pd.DataFrame(rows)


def key_findings(
    summary: pd.DataFrame,
    effects: pd.DataFrame,
    cells: pd.DataFrame,
    best: pd.DataFrame,
    reach: pd.DataFrame,
) -> List[str]:
    """Bullet points that a Results section can quote directly."""
    out = []
    lo, hi = summary.load_tps.min(), summary.load_tps.max()

    for _, row in best.iterrows():
        out.append(
            f"On {TOPOLOGY_LABELS.get(row.topology, row.topology)} the best static "
            f"configuration is **{_cfg(row.c_best)}**, stable up to "
            f"{row.max_sustainable_tps} tx/s with a mean p99 of "
            f"{row.p99_mean_ms:.0f} ms ({row.reason})."
        )

    p99 = effects[effects.metric == "p99_ms"]
    strongest = p99.loc[p99.delta_improvement_ms.idxmax()]
    out.append(
        f"The largest paired improvement of the primary endpoint is "
        f"{strongest.delta_improvement_ms:.0f} ms "
        f"(95 % CI {strongest.ci_low:.0f} to {strongest.ci_high:.0f} ms) for "
        f"{_cfg(strongest.profile)} on "
        f"{TOPOLOGY_LABELS.get(strongest.topology, strongest.topology)} at "
        f"{strongest.load_tps} tx/s."
    )

    strict = reach.groupby("config").max_tps_all_repeats.min()
    majority = reach.groupby("config").max_tps_majority.min()
    out.append(
        "Largest load that stays stable across every topology, strict rule "
        "(all repeats) / majority rule: "
        + "; ".join(
            f"{_cfg(c)} {strict[c]} / {majority[c]} tx/s" for c in strict.index
        )
        + f" (the campaign offered up to {hi} tx/s)."
    )
    disagree = reach[~reach.rules_agree]
    if len(disagree):
        out.append(
            f"The two pre-registered rules disagree in {len(disagree)} "
            "config-topology combinations ("
            + "; ".join(
                f"{_cfg(r.config)} on {TOPOLOGY_LABELS.get(r.topology, r.topology)}"
                for _, r in disagree.iterrows()
            )
            + "). Those cells sit on the stability boundary and are exactly where "
            "the precision rule calls for additional repeats before a claim is made."
        )
    failures = cells[~cells.stable_all]
    if len(failures):
        out.append(
            f"{len(failures)} of {len(cells)} cells failed at least one "
            "pre-registered criterion of Tab. 13; the run-level reasons are in "
            "`run_stability.csv` under `failed_criteria`."
        )

    cpu_lo = summary[summary.load_tps == lo].groupby("config").cpu_p95_pct.mean()
    if len(cpu_lo) >= 2:
        out.append(
            f"Shorter pacing costs CPU even when the chain is nearly idle: at "
            f"{lo} tx/s the validator CPU p95 rises from "
            f"{cpu_lo.min():.0f} % ({_cfg(cpu_lo.idxmin())}) to "
            f"{cpu_lo.max():.0f} % ({_cfg(cpu_lo.idxmax())}), which is the "
            f"mechanism behind RQ2."
        )

    conv = summary.groupby("topology").convergence_p99_ms.mean()
    out.append(
        "Convergence between the two independent read nodes (eq. 7) has a p99 of "
        + ", ".join(
            f"{v:.0f} ms on {TOPOLOGY_LABELS.get(k, k)}" for k, v in conv.items()
        )
        + f"; the floor of {POLL_S * 1000:.0f} ms is the client polling grid, not "
        "a property of the network."
    )
    return out


def write_report(
    out_dir: Path,
    profile_name: str,
    provenance: str,
    summary: pd.DataFrame,
    effects: pd.DataFrame,
    stability: pd.DataFrame,
    cells: pd.DataFrame,
    best: pd.DataFrame,
    reach: pd.DataFrame,
    t14: pd.DataFrame,
    t15: pd.DataFrame,
    t16: pd.DataFrame,
    precision: pd.DataFrame,
) -> Dict[str, Path]:
    """Write RESULTS.md, RESULTS_UK.md and the LaTeX article fragment."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    profile = get_profile(profile_name)
    verdicts = hypothesis_verdicts(summary, effects, cells)
    findings = key_findings(summary, effects, cells, best, reach)
    measured = provenance == "MEASURED"

    def head(md_banner: str) -> str:
        return "" if measured else md_banner.format(prov=provenance) + "\n\n"

    en = []
    en.append("# Results\n")
    en.append(head(BANNER_EN))
    en.append(
        f"Campaign profile `{profile.name}`: {profile.n_runs} runs "
        f"({len(profile.configs)} configurations x {len(profile.topologies)} topologies "
        f"x {len(profile.loads_tps)} loads x {profile.repeats} repeats), "
        f"{profile.warmup_s} s warm-up, {profile.measure_s} s measurement, "
        f"{profile.drain_s} s drain, {profile.n_scheduled_tx:,} scheduled transactions "
        f"in the measurement windows, {profile.wall_clock_s / 3600:.2f} h of minimum "
        f"machine time. Load is generated by {N_CLIENTS} workstations replaying "
        f"immutable traces; the inferential unit is the run.\n"
    )
    en.append("\n## Key findings\n")
    en.extend(f"- {f}\n" for f in findings)

    en.append("\n## Pre-registered hypotheses\n\n")
    en.append(
        to_markdown(
            verdicts.assign(supported=verdicts.supported.map({True: "supported",
                                                              False: "not supported"}))
        )
        + "\n"
    )
    en.append("\n## Tab. 14 — quantiles of user-visible latency\n\n")
    en.append(to_markdown(t14) + "\n")
    en.append("\n## Tab. 15 — stability, goodput and resources\n\n")
    en.append(to_markdown(t15) + "\n")
    en.append("\n## Tab. 16 — paired effects against C0 with 95 % CI\n\n")
    en.append(to_markdown(t16) + "\n")
    en.append("\n## Maximum sustainable load\n\n")
    en.append(to_markdown(reach) + "\n")
    en.append("\n## Best static configuration\n\n")
    en.append(to_markdown(best) + "\n")

    need = precision[precision.needs_more_repeats]
    en.append("\n## Precision rule\n\n")
    en.append(
        f"The protocol adds repeats in blocks of {5} (up to 30) wherever the 95 % CI "
        f"of the primary endpoint has a relative half-width above 10 %. "
        + (
            f"{len(need)} of {len(precision)} strata trigger the rule in this dataset.\n\n"
            + to_markdown(need.head(20)) + "\n"
            if len(need)
            else "No stratum triggers the rule in this dataset.\n"
        )
    )

    en.append("\n## Stability rules applied\n\n")
    for k, v in THRESHOLDS.as_dict().items():
        en.append(f"- `{k}` = {v}\n")

    en.append("\n## Outstanding data\n\n")
    en.append(
        "A real campaign must supply the following before any number here is "
        "reported as a measurement:\n\n"
    )
    en.extend(f"- [ ] `{f}`\n" for f in DATA_REQUIRED_FIELDS)

    (out_dir / "RESULTS.md").write_text("".join(en), encoding="utf-8")

    uk = []
    uk.append("# Результати\n")
    uk.append("" if measured else BANNER_UK.format(prov=provenance) + "\n\n")
    uk.append(
        f"Профіль кампанії `{profile.name}`: {profile.n_runs} прогонів "
        f"({len(profile.configs)} конфігурацій x {len(profile.topologies)} топологій "
        f"x {len(profile.loads_tps)} рівнів навантаження x {profile.repeats} повторів), "
        f"{profile.warmup_s} с прогрівання, {profile.measure_s} с вимірювання, "
        f"{profile.drain_s} с завершення, {profile.n_scheduled_tx:,} запланованих "
        f"транзакцій у вимірювальних вікнах, {profile.wall_clock_s / 3600:.2f} год "
        f"мінімального машинного часу. Навантаження створюють {N_CLIENTS} робочих "
        f"місць, що відтворюють незмінні траси; одиницею аналізу є прогін.\n"
    )
    uk.append("\n## Основні висновки\n")
    uk.extend(f"- {f}\n" for f in findings)
    uk.append("\n## Попередньо зареєстровані гіпотези\n\n")
    uk.append(
        to_markdown(
            verdicts.assign(
                supported=verdicts.supported.map({True: "підтверджено",
                                                  False: "не підтверджено"})
            )
        )
        + "\n"
    )
    uk.append("\n## Таблиця 14 — квантілі користувацько-видимої затримки\n\n")
    uk.append(to_markdown(t14) + "\n")
    uk.append("\n## Таблиця 15 — стійкість, пропускна здатність і ресурси\n\n")
    uk.append(to_markdown(t15) + "\n")
    uk.append("\n## Таблиця 16 — ефекти відносно C0 з 95 % довірчими інтервалами\n\n")
    uk.append(to_markdown(t16) + "\n")
    uk.append("\n## Максимальне стійке навантаження\n\n")
    uk.append(to_markdown(reach) + "\n")
    uk.append("\n## Найкраща статична конфігурація\n\n")
    uk.append(to_markdown(best) + "\n")
    uk.append("\n## Відсутні дані\n\n")
    uk.extend(f"- [ ] `{f}`\n" for f in DATA_REQUIRED_FIELDS)
    (out_dir / "RESULTS_UK.md").write_text("".join(uk), encoding="utf-8")

    fragment = _article_fragment(profile, provenance, summary, best, reach, verdicts)
    (out_dir / "article_fragment.tex").write_text(fragment, encoding="utf-8")

    verdicts.to_csv(out_dir / "hypothesis_verdicts.csv", index=False,
                    lineterminator="\n")
    return {
        "results_en": out_dir / "RESULTS.md",
        "results_uk": out_dir / "RESULTS_UK.md",
        "fragment": out_dir / "article_fragment.tex",
    }


def _article_fragment(profile, provenance, summary, best, reach, verdicts) -> str:
    """Experimental-setup paragraph of protocol section 17, with numbers."""
    topo_note = (
        "local, two-site VPN, and emulated three-region topologies"
        if len(profile.topologies) == 3
        else "the topologies listed in the protocol"
    )
    lines = [
        "% Generated by alp.report -- regenerate rather than edit by hand.",
        f"% Data provenance: {provenance}.",
    ]
    if provenance != "MEASURED":
        lines.append(
            "% WARNING: reference-model output. Replace with campaign results "
            "before submission."
        )
    lines += [
        "\\subsection{Experimental Setup}",
        "The field evaluation was conducted on the two-site cyber range of the "
        "University of Customs and Finance, with the sites interconnected through a "
        f"protected VPN. {N_CLIENTS} Kali Linux workstations generated identical "
        "precomputed transaction traces. A permissioned Avalanche L1 based on "
        "Subnet-EVM used five validators and two independent read nodes. We compared "
        "the stock configuration with minimum block-delay profiles of 1000, 750, 500 "
        f"and 250\\,ms under {topo_note}. Each condition was repeated "
        f"{profile.repeats} times using a randomized blocked schedule. A run "
        f"comprised a {profile.warmup_s}\\,s warm-up, a {profile.measure_s}\\,s "
        f"measurement window and a {profile.drain_s}\\,s drain period. The primary "
        "metric, $T_\\mathrm{visible}$, was measured on the load generator using a "
        "monotonic nanosecond clock from raw-transaction submission until the first "
        "independent read returned the accepted updated state. Run-level $p_{50}$, "
        "$p_{95}$ and $p_{99}$ values were compared using paired bootstrap "
        "confidence intervals.",
        "",
        "\\subsection{Results}",
    ]
    for _, row in best.iterrows():
        topology = tex_escape(TOPOLOGY_LABELS.get(row.topology, row.topology))
        lines.append(
            f"On the {topology} topology the "
            f"best static configuration was {tex_escape(row.c_best)}, stable up to "
            f"{row.max_sustainable_tps}\\,tx/s with a mean $p_{{99}}$ of "
            f"{row.p99_mean_ms:.0f}\\,ms."
        )
    for _, row in verdicts.iterrows():
        state = "supported" if row.supported else "not supported"
        # Escaped: the evidence strings carry per-cent signs, which would
        # otherwise comment out the rest of the LaTeX line.
        lines.append(
            f"Hypothesis {row.hypothesis} was {state}: {tex_escape(row.evidence)}."
        )
    return "\n".join(lines) + "\n"
