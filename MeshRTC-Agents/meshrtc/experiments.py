"""
Batch experiments (paired Monte Carlo) and their result figures.
Sizes are reduced so that the whole notebook runs in a few minutes on Colab;
increase ``reps`` for publication-grade confidence intervals.
"""
from __future__ import annotations

import itertools
import time

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .sim import Config, Sim, run_paired
from .fleet import FleetLogic
from .viz import STRAT_COLOR, C


def ci95(p, n):
    p = np.asarray(p, float)
    return 1.96 * np.sqrt(np.maximum(p * (1 - p), 1e-9) / np.maximum(n, 1))


# =========================================================================== A. single missions
def single_missions(world, socs=(0.3, 0.5, 0.7, 0.9), Hs=(6, 72), ks=(0, 4), bs=(0.0, 0.05, 0.1, 0.2),
                    reps=8, strategies=("S1", "S2", "S3"), seed0=10_000, **cfg_kw):
    rows = []
    sites = [f"R{i}" for i in range(1, 9)]
    t0 = time.time()
    for H, k, soc in itertools.product(Hs, ks, socs):
        for r in range(reps):
            seed = seed0 + r * 1000 + int(soc * 10)      # same seed across H and k: paired over comm factors
            rng = np.random.default_rng(seed)
            b = float(rng.choice(bs))
            site = str(rng.choice(sites))
            alt = str(rng.choice([s for s in sites if s != site]))
            cfg = Config(H=H, k=k, b=b, soc0=soc, tasks=[dict(site=site, alt=alt)], **cfg_kw)
            out = run_paired(world, cfg, strategies, seed=seed)
            for s, sim in out.items():
                m = sim.mission_metrics()[0]
                m.update(H=H, k=k, b=b, soc0=soc, seed=seed, site=site)
                rows.append(m)
    df = pd.DataFrame(rows)
    df.attrs["seconds"] = time.time() - t0
    return df


def summary_table(df, by="strategy"):
    g = df.groupby(by)
    out = pd.DataFrame({
        "missions": g.size(),
        "on-time %": 100 * g["on_time"].mean(),
        "valid %": 100 * g["valid"].mean(),
        "stranded %": 100 * g["stranded"].mean(),
        "recovered %": 100 * g["recovered"].mean(),
        "SoC at end %": 100 * g["soc_end"].mean(),
        "receipt latency, min (median)": g["lat"].median(),
    })
    return out.round(1)


def plot_single(df):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4))
    strats = list(dict.fromkeys(df["strategy"]))
    socs = sorted(df["soc0"].unique())
    x = np.arange(len(socs))
    w = 0.8 / len(strats)
    for j, (metric, title) in enumerate((("on_time", "on-time delivery"), ("stranded", "robot stranded"),
                                         ("recovered", "robot recovered"))):
        ax = axs[j]
        for i, s in enumerate(strats):
            d = df[df.strategy == s].groupby("soc0")[metric]
            p, n = d.mean().reindex(socs).values, d.size().reindex(socs).values
            ax.bar(x + (i - (len(strats) - 1) / 2) * w, 100 * p, w * 0.92, yerr=100 * ci95(p, n),
                   color=STRAT_COLOR.get(s, C["ink"]), label=s, capsize=2, error_kw=dict(lw=0.8, ecolor=C["ink2"]))
        ax.set_xticks(x, [f"{s:.0%}" for s in socs])
        ax.set_xlabel("initial state of charge")
        ax.set_ylabel("%")
        ax.set_ylim(0, 105)
        ax.set_title(title)
    axs[0].legend(ncol=len(strats))
    return fig


def outcome_mix(df):
    order = ["recovered", "held", "declined", "stopped", "stuck", "depleted", "travelling"]
    cols = {"recovered": C["green"], "held": C["yellow"], "declined": C["aqua"], "stopped": C["violet"],
            "stuck": C["orange"], "depleted": C["red"], "travelling": C["magenta"]}
    tab = pd.crosstab(df["strategy"], df["terminal"], normalize="index").reindex(columns=order).fillna(0)
    fig, ax = plt.subplots(figsize=(9, 2.6 + 0.35 * len(tab)))
    left = np.zeros(len(tab))
    for k in order:
        v = tab[k].values
        if v.sum() == 0:
            continue
        ax.barh(tab.index, 100 * v, left=100 * left, color=cols[k], label=k, edgecolor=C["surface"], lw=2)
        for i, (vv, ll) in enumerate(zip(v, left)):
            if vv > 0.06:
                ax.text(100 * (ll + vv / 2), i, f"{vv:.0%}", ha="center", va="center", color="white", fontsize=8.5,
                        weight="bold")
        left += v
    ax.set_xlabel("% of missions")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    ax.set_title("How missions end")
    ax.grid(False)
    return fig


# =========================================================================== B. risk dial
def risk_dial(world, zs=(0.0, 0.67, 1.28, 2.33), socs=(0.3, 0.5, 0.7), reps=12, seed0=40_000):
    rows = []
    sites = [f"R{i}" for i in range(1, 9)]
    for soc, r in itertools.product(socs, range(reps)):
        seed = seed0 + r * 100 + int(soc * 10)
        rng = np.random.default_rng(seed)
        site = str(rng.choice(sites))
        for z in zs:
            for ow in (False, True):
                cfg = Config(H=24, k=2, b=float(rng.choice([0, 0.05, 0.1])), soc0=soc, z=z, oneway=ow,
                             tasks=[dict(site=site, alt="R5" if site != "R5" else "R1")])
                m = Sim(world, cfg, seed=seed, strategy="S3").run().mission_metrics()[0]
                m.update(z=z, oneway=ow, soc0=soc)
                rows.append(m)
    return pd.DataFrame(rows)


def plot_risk_dial(df):
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for ow, ls in ((False, "-"), (True, "--")):
        for soc, col in zip(sorted(df.soc0.unique()), [C["orange"], C["blue"], C["aqua"]]):
            d = df[(df.oneway == ow) & (df.soc0 == soc)].groupby("z")
            x, y = 100 * d["stranded"].mean() + 100 * (d["terminal"].apply(lambda s: (s == "held").mean())), 100 * d["on_time"].mean()
            ax.plot(x, y, ls, marker="o", color=col, lw=2, ms=7,
                    label=f"SoC {soc:.0%}{' one-way' if ow else ''}")
            for z, xx, yy in zip(d.groups.keys(), x, y):
                ax.annotate(f"z={z}", (xx, yy), xytext=(4, 3), textcoords="offset points", fontsize=7.5, color=C["ink2"])
    ax.set_xlabel("robot not back at a recovery point (stranded or held at site), %")
    ax.set_ylabel("on-time delivery, %")
    ax.set_title("Risk dial z: delivery vs robot recovery (S3)")
    ax.legend(fontsize=8)
    return fig


# =========================================================================== C. fleet
def fleet_experiment(world, ks=(0, 4, 8), Ms=(4,), reps=6, H=72, policies=("C", "A"), seed0=500):
    rows = []
    for k, M, r in itertools.product(ks, Ms, range(reps)):
        for pol in policies:
            cfg = Config(fleet=True, policy=pol, n_robots=M, H=H, k=k, b=0.05, p_close=0)
            sim = Sim(world, cfg, seed=seed0 + 37 * r).run()     # same demand across k and policies
            m = FleetLogic.metrics(sim)
            m.update(k=k, M=M, rep=r)
            rows.append(m)
    return pd.DataFrame(rows)


def plot_fleet(df):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4))
    ks = sorted(df.k.unique())
    x = np.arange(len(ks))
    for i, pol in enumerate(["C", "A"]):
        d = df[df.policy == pol].groupby("k")
        lab = "Centralized" if pol == "C" else "Agentic (spare + DTN + auction)"
        for ax, met, sc in ((axs[0], "service", 100), (axs[1], "aware_med", 1), (axs[2], "lat_med", 1)):
            mu = d[met].mean().reindex(ks).values * sc
            sd = d[met].std().reindex(ks).values * sc / np.sqrt(d.size().reindex(ks).values)
            ax.bar(x + (i - 0.5) * 0.38, mu, 0.36, yerr=1.96 * sd, color=STRAT_COLOR[pol], label=lab, capsize=2,
                   error_kw=dict(lw=0.8, ecolor=C["ink2"]))
    for ax, t, yl in ((axs[0], "on-time service", "%"), (axs[1], "time until a request is known, median", "min"),
                      (axs[2], "receipt confirmation latency, median", "min")):
        ax.set_xticks(x, [f"k={k}" for k in ks])
        ax.set_title(t)
        ax.set_ylabel(yl)
    axs[0].legend(fontsize=8)
    return fig


# =========================================================================== D. neural comparison
def neural_comparison(world, energy_model, policy_model, socs=(0.3, 0.45, 0.6, 0.8), reps=20, seed0=7000):
    rows, shield = [], []
    for soc, r in itertools.product(socs, range(reps)):
        seed = seed0 + r + int(soc * 100) * 50
        cfg = Config(soc0=soc, H=24, k=2, b=0.1, energy_model=energy_model, policy_model=policy_model)
        out = run_paired(world, cfg, ("S3", "S3N", "NNP"), seed=seed)
        for s, sim in out.items():
            m = sim.mission_metrics()[0]
            m.update(soc0=soc, shield=len(sim.shield_events),
                     mid_abort=any(d[2] == "RET" for d in sim.robots[0].decisions),
                     nn_disagree=sum(a != b for a, b, _ in sim.nn_actions))
            rows.append(m)
            shield += sim.shield_events
    return pd.DataFrame(rows), shield
