"""Leakage-resistant evaluation manifests, and the audit that proves it.

Every partition is built at *group* level and then expanded to records, never the
other way round. The groups differ by manifest:

    event_disjoint          the event
    location_holdout        the generalized site group
    time_holdout            a contiguous collection block, with an embargo gap
    source_holdout          the contributor or device group
    hard_negative_challenge the negative-event family, balanced by event

Near-duplicate media groups are an additional constraint on all of them: two
objects in one duplicate group must land in the same partition, or the same
content appears on both sides of the split and every reported score is optimistic.

The audit at the end is not decoration. A split builder is exactly the kind of
code whose bugs are invisible - the manifests look fine and the scores merely come
out too high - so the invariant is asserted rather than assumed.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from . import timebase as tb
from .config import Config


def _allocate(groups: Sequence[str], weights: Dict[str, int], fractions: Dict[str, float],
              seed: int) -> Dict[str, str]:
    """Greedy weighted allocation of groups to partitions.

    Groups differ in size, so allocating them by count would produce partitions
    whose *record* proportions are wrong. Sorting by descending weight and
    repeatedly assigning to whichever partition is furthest below its target is
    the standard largest-first heuristic; it is deterministic given the seed and
    it keeps the record split close to the requested fractions without ever
    splitting a group.
    """
    rng = np.random.default_rng(seed)
    order = sorted(groups, key=lambda g: (-weights.get(g, 0), g))
    total = sum(weights.get(g, 0) for g in order) or 1
    targets = {k: v * total for k, v in fractions.items()}
    current = {k: 0.0 for k in fractions}
    out: Dict[str, str] = {}
    for g in order:
        deficits = {k: targets[k] - current[k] for k in fractions}
        best = max(deficits, key=lambda k: (deficits[k], rng.random()))
        out[g] = best
        current[best] += weights.get(g, 0)
    return out


def _event_weights(events: pd.DataFrame, media: pd.DataFrame,
                   observations: pd.DataFrame) -> Dict[str, int]:
    """Weight an event by everything derived from it, not by its single row."""
    w = {e: 1 for e in events["event_id"]}
    for df in (observations, media):
        if df is not None and not df.empty and "event_id" in df.columns:
            for eid, n in df["event_id"].value_counts().items():
                w[eid] = w.get(eid, 0) + int(n)
    return w


def _duplicate_constraint(events: pd.DataFrame, media: pd.DataFrame) -> Dict[str, str]:
    """Merge events that share a near-duplicate media group into one super-group.

    This is the constraint that a purely event-level split misses: two distinct
    events can contain re-encodings of the same recording, and separating the
    events does not separate the content.
    """
    parent = {e: e for e in events["event_id"]}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    if media is not None and not media.empty:
        for _, grp in media.groupby("duplicate_group"):
            eids = [e for e in grp["event_id"].unique() if e in parent]
            for other in eids[1:]:
                union(eids[0], other)
    return {e: find(e) for e in parent}


#: What each manifest guarantees. The audit checks the stated constraint, not a
#: single generic one: ``hard_negative_challenge`` deliberately spreads every
#: confounder family across all three partitions, so auditing it for
#: group-disjointness would flag its defining property as a defect.
CONSTRAINT_KIND = {
    "event_disjoint": "group_disjoint",
    "location_holdout": "group_disjoint",
    "time_holdout": "temporal_block",
    "source_holdout": "group_disjoint",
    "hard_negative_challenge": "balanced_by_group",
}


def build_manifests(events: pd.DataFrame, observations: pd.DataFrame,
                    media: pd.DataFrame, cfg: Config, seed: int = 17
                    ) -> Dict[str, pd.DataFrame]:
    """Build every canonical manifest of Table 6."""
    fr = {"train": cfg["splits"]["train"], "val": cfg["splits"]["val"],
          "test": cfg["splits"]["test"]}
    weights = _event_weights(events, media, observations)
    dup_parent = _duplicate_constraint(events, media)
    out: Dict[str, pd.DataFrame] = {}

    # -- event_disjoint, respecting the near-duplicate constraint ------------ #
    super_weights: Dict[str, int] = {}
    for eid, root in dup_parent.items():
        super_weights[root] = super_weights.get(root, 0) + weights.get(eid, 1)
    alloc = _allocate(list(super_weights), super_weights, fr, seed)
    out["event_disjoint"] = pd.DataFrame({
        "event_id": events["event_id"],
        "partition": [alloc[dup_parent[e]] for e in events["event_id"]],
        "group_key": [dup_parent[e] for e in events["event_id"]],
    })

    # -- location_holdout ---------------------------------------------------- #
    site_w: Dict[str, int] = {}
    for eid, sg in zip(events["event_id"], events["site_group_id"]):
        site_w[sg] = site_w.get(sg, 0) + weights.get(eid, 1)
    alloc = _allocate(list(site_w), site_w, fr, seed + 1)
    out["location_holdout"] = pd.DataFrame({
        "event_id": events["event_id"],
        "partition": [alloc[sg] for sg in events["site_group_id"]],
        "group_key": events["site_group_id"].to_numpy(),
    })

    # -- time_holdout, with an embargo gap ----------------------------------- #
    out["time_holdout"] = _time_holdout(events, cfg, fr)

    # -- source_holdout ------------------------------------------------------ #
    out["source_holdout"] = _source_holdout(events, observations, fr, weights, seed + 2)

    # -- hard_negative_challenge --------------------------------------------- #
    out["hard_negative_challenge"] = _negative_challenge(events, fr, seed + 3)

    # The near-duplicate constraint applies to every manifest, not only to the
    # event-disjoint one. It is applied last so that each manifest's own
    # construction stays readable.
    modes = {"event_disjoint": "move", "location_holdout": "exclude",
             "time_holdout": "exclude", "source_holdout": "exclude",
             "hard_negative_challenge": "move"}
    for name in out:
        out[name] = enforce_duplicate_constraint(out[name], media, modes[name])
    return out


def _time_holdout(events: pd.DataFrame, cfg: Config,
                  fr: Dict[str, float]) -> pd.DataFrame:
    """Chronological blocks separated by an embargo gap.

    The gap is what makes the manifest mean anything. Adjacent blocks share
    weather, aircraft, crews, and sensor calibration, so a split that merely cuts
    the timeline still lets a model exploit conditions it has already seen. Events
    that fall inside a gap are excluded from every partition, and the manifest
    says so rather than quietly absorbing them.
    """
    gap_ns = int(cfg["splits"]["temporal_gap_days"]) * 86_400 * tb.NS
    ev = events.sort_values("t_start_utc_ns").reset_index(drop=True)
    t = ev["t_start_utc_ns"].astype("int64").to_numpy()
    span = t.max() - t.min()
    b1 = t.min() + int(span * fr["train"])
    b2 = t.min() + int(span * (fr["train"] + fr["val"]))

    partition: List[str] = []
    for ts in t:
        if ts < b1 - gap_ns / 2:
            partition.append("train")
        elif ts < b1 + gap_ns / 2:
            partition.append("embargo")
        elif ts < b2 - gap_ns / 2:
            partition.append("val")
        elif ts < b2 + gap_ns / 2:
            partition.append("embargo")
        else:
            partition.append("test")
    return pd.DataFrame({"event_id": ev["event_id"], "partition": partition,
                         "group_key": [f"block:{p}" for p in partition]})


def _source_holdout(events: pd.DataFrame, observations: pd.DataFrame,
                    fr: Dict[str, float], weights: Dict[str, int],
                    seed: int) -> pd.DataFrame:
    """Withhold contributor and device groups where sample size permits.

    An event usually carries several sources, so a strict source-disjoint
    partition is not achievable without discarding events. The manifest therefore
    groups each event by its *dominant* source and marks events whose sources
    straddle a partition boundary as ``ambiguous`` rather than assigning them and
    pretending the holdout is clean.
    """
    if observations is None or observations.empty:
        return pd.DataFrame({"event_id": events["event_id"],
                             "partition": "train", "group_key": "none"})
    dom = (observations.groupby(["event_id", "source_id"]).size()
           .reset_index(name="n").sort_values("n", ascending=False)
           .drop_duplicates("event_id").set_index("event_id")["source_id"])
    src_w: Dict[str, int] = {}
    for eid in events["event_id"]:
        s = dom.get(eid, "none")
        src_w[s] = src_w.get(s, 0) + weights.get(eid, 1)
    alloc = _allocate(list(src_w), src_w, fr, seed)

    partitions, keys = [], []
    obs_sources = observations.groupby("event_id")["source_id"].apply(set)
    for eid in events["event_id"]:
        s = dom.get(eid, "none")
        p = alloc.get(s, "train")
        others = {alloc.get(x, p) for x in obs_sources.get(eid, {s})}
        partitions.append(p if others == {p} else "ambiguous")
        keys.append(s)
    return pd.DataFrame({"event_id": events["event_id"], "partition": partitions,
                         "group_key": keys})


def _negative_challenge(events: pd.DataFrame, fr: Dict[str, float],
                        seed: int) -> pd.DataFrame:
    """Balance negative families by event, not by frame.

    Balancing by frame lets one long helicopter recording dominate the confounder
    class and makes the stress test a measurement of that one recording.
    """
    rng = np.random.default_rng(seed)
    partitions, keys = [], []
    for kind, neg in zip(events["event_kind"], events["hard_negative_type"]):
        keys.append(neg if kind == "negative_control" else f"positive:{kind}")
    ev = events.assign(group_key=keys)
    assign: Dict[str, str] = {}
    for key, grp in ev.groupby("group_key"):
        n = len(grp)
        order = rng.permutation(n)
        cuts = [int(n * fr["train"]), int(n * (fr["train"] + fr["val"]))]
        for rank, idx in enumerate(order):
            eid = grp["event_id"].iloc[idx]
            assign[eid] = ("train" if rank < cuts[0]
                           else ("val" if rank < cuts[1] else "test"))
    return pd.DataFrame({"event_id": ev["event_id"],
                         "partition": [assign[e] for e in ev["event_id"]],
                         "group_key": ev["group_key"].to_numpy()})


# --------------------------------------------------------------------------- #
# Audit

def enforce_duplicate_constraint(man: pd.DataFrame, media: pd.DataFrame,
                                 mode: str) -> pd.DataFrame:
    """Resolve near-duplicate groups that straddle a partition.

    For a manifest grouped by something other than the event - a site group, a
    time block - the two constraints can genuinely conflict: the same recording
    can be re-encoded at two different sites, and no assignment satisfies both
    location disjointness and duplicate disjointness. The conflict is resolved
    explicitly rather than silently:

    ``move``     the manifest's own grouping is soft, so every event in the
                 duplicate group joins the partition holding most of it. This is
                 right for the hard-negative challenge, where family balance is a
                 preference and content leakage is not.
    ``exclude``  the manifest's own grouping is the point of the manifest, so the
                 conflicting events leave every partition and are reported as
                 excluded. A smaller clean holdout is worth more than a larger
                 one whose transfer claim is contaminated.
    """
    if media is None or media.empty:
        return man
    out = man.copy()
    part = dict(zip(out["event_id"], out["partition"]))
    for _, grp in media.groupby("duplicate_group"):
        eids = [e for e in grp["event_id"].unique() if e in part]
        parts = {part[e] for e in eids} - {"embargo", "ambiguous"}
        if len(parts) <= 1:
            continue
        if mode == "move":
            counts = pd.Series([part[e] for e in eids
                                if part[e] not in ("embargo", "ambiguous")]).value_counts()
            target = counts.idxmax()
            for e in eids:
                part[e] = target
        else:
            for e in eids:
                part[e] = "duplicate_conflict"
    out["partition"] = [part[e] for e in out["event_id"]]
    return out


# --------------------------------------------------------------------------- #
def audit(manifests: Dict[str, pd.DataFrame], events: pd.DataFrame,
          media: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Assert that each manifest's own grouping constraint actually holds.

    Two invariants are checked. The first is manifest-specific: a
    ``group_disjoint`` manifest must place every group in exactly one partition,
    a ``temporal_block`` manifest must keep its blocks ordered and separated by
    the embargo, and a ``balanced_by_group`` manifest must instead show every
    sufficiently large group represented across partitions. The second is
    universal: no near-duplicate media group may straddle a partition, whatever
    the manifest.

    Asserting rather than assuming matters here more than anywhere else in the
    pipeline. A split bug produces manifests that look entirely normal and scores
    that are merely too good, so nothing downstream would ever surface it.
    """
    rows: List[dict] = []
    gap_ns = int(cfg["splits"]["temporal_gap_days"]) * 86_400 * tb.NS
    t_by_event = dict(zip(events["event_id"], events["t_start_utc_ns"].astype("int64")))

    for name, man in manifests.items():
        kind = CONSTRAINT_KIND.get(name, "group_disjoint")
        real = man[~man["partition"].isin(
            ["embargo", "ambiguous", "duplicate_conflict"])]
        violations = 0
        detail = ""

        if kind == "group_disjoint":
            by_group = real.groupby("group_key")["partition"].nunique()
            violations = int((by_group > 1).sum())
            detail = "one partition per group"
        elif kind == "temporal_block":
            times = {p: [t_by_event[e] for e in g["event_id"] if e in t_by_event]
                     for p, g in real.groupby("partition")}
            spans = {p: (min(v), max(v)) for p, v in times.items() if v}
            order = sorted(spans.items(), key=lambda kv: kv[1][0])
            gaps = []
            for (_, a), (_, b) in zip(order, order[1:]):
                if b[0] <= a[1]:
                    violations += 1
                else:
                    gaps.append(b[0] - a[1])
            violations += sum(1 for g in gaps if g < gap_ns)
            detail = (f"blocks ordered; min observed gap "
                      f"{min(gaps) / (86_400 * tb.NS):.1f} d vs required "
                      f"{gap_ns / (86_400 * tb.NS):.0f} d"
                      if gaps else "single block")
        else:  # balanced_by_group
            by_group = real.groupby("group_key")["partition"].nunique()
            sizes = real.groupby("group_key").size()
            violations = int(((by_group < 2) & (sizes >= 3)).sum())
            detail = "each family of 3+ events represented in >1 partition"

        dup_violations = 0
        if media is not None and not media.empty:
            part = dict(zip(man["event_id"], man["partition"]))
            for _, grp in media.groupby("duplicate_group"):
                parts = {part.get(e) for e in grp["event_id"].unique()}
                parts -= {None, "embargo", "ambiguous"}
                if len(parts) > 1:
                    dup_violations += 1

        counts = man["partition"].value_counts().to_dict()
        rows.append({
            "manifest": name, "constraint": kind, "n_events": len(man),
            "n_groups": int(man["group_key"].nunique()),
            "constraint_violations": violations,
            "near_duplicate_violations": dup_violations,
            "train": counts.get("train", 0), "val": counts.get("val", 0),
            "test": counts.get("test", 0),
            "excluded": (counts.get("embargo", 0) + counts.get("ambiguous", 0)
                         + counts.get("duplicate_conflict", 0)),
            "excluded_duplicate_conflict": counts.get("duplicate_conflict", 0),
            # An empty partition is the symptom that matters: with fewer groups
            # than partitions, or with one group dominating, a holdout silently
            # degenerates into a two-way split and the validation set vanishes.
            "warning": ("empty_partition:too_few_groups"
                        if min(counts.get("train", 0), counts.get("val", 0),
                               counts.get("test", 0)) == 0 else ""),
            "status": "pass" if violations == 0 and dup_violations == 0 else "FAIL",
            "detail": detail,
        })
    return pd.DataFrame(rows)
