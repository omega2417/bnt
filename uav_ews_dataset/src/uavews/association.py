"""Window construction and uncertainty-expanded multimodal association.

The rule the manuscript states is deliberately conservative: an observation is
attached to a window only when its *uncertainty-expanded* interval overlaps the
window by at least the configured minimum, or when an expert documents the
relation. Nothing is attached on geographic proximity alone.

Two properties follow, and both matter more than the association rate:

* A source with a poor clock is not silently attached to the wrong window.
  Expanding its interval by k sigma before the overlap test means a mobile report
  with 1.5 s of clock uncertainty can only be attached where a 1.5 s error would
  not change the answer.
* The expansion cuts both ways. A wide interval overlaps *more* windows, so a
  badly synchronized source produces ambiguous associations rather than
  confidently wrong ones. Ambiguity is resolved by taking the window of maximum
  overlap and recording the runner-up margin, so a downstream user can filter on
  how decisive the association was.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from . import ids, timebase as tb
from .config import Config


def build_windows(events: pd.DataFrame, cfg: Config, salt: bytes) -> pd.DataFrame:
    """Tile every event with pre-event, event, and post-event windows.

    The pre- and post-event windows are not padding. The pre-event interval is
    where an early-warning model must operate - before the anchor exists - and
    the post-event interval carries the negative evidence that separates a target
    that left from a target that was never there.
    """
    w = cfg["windows"]
    pre = tb.seconds_to_ns(float(w["pre_event_s"]))
    post = tb.seconds_to_ns(float(w["post_event_s"]))
    rows: List[dict] = []

    for _, ev in events.iterrows():
        eid = ev["event_id"]
        t0, t1 = int(ev["t_start_utc_ns"]), int(ev["t_end_utc_ns"])
        idx = 0
        rows.append({"window_id": ids.window_id(salt, eid, idx), "event_id": eid,
                     "window_role": "pre_event", "w_start_utc_ns": t0 - pre,
                     "w_end_utc_ns": t0, "window_index": idx})
        idx += 1
        for (a, b) in tb.tile_windows(t0, t1, float(w["window_span_s"]),
                                      float(w["window_hop_s"])):
            rows.append({"window_id": ids.window_id(salt, eid, idx), "event_id": eid,
                         "window_role": "event", "w_start_utc_ns": a,
                         "w_end_utc_ns": b, "window_index": idx})
            idx += 1
        rows.append({"window_id": ids.window_id(salt, eid, idx), "event_id": eid,
                     "window_role": "post_event", "w_start_utc_ns": t1,
                     "w_end_utc_ns": t1 + post, "window_index": idx})
    return pd.DataFrame(rows)


def associate(observations: pd.DataFrame, windows: pd.DataFrame,
              sources: pd.DataFrame, cfg: Config
              ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Attach observations to windows, and report the association diagnostics.

    Returns the observations with ``window_id`` filled where the overlap test
    passed, plus a per-observation diagnostic frame carrying the expansion width,
    the best and runner-up overlaps, and the decision.
    """
    k = float(cfg["synchronization"]["uncertainty_expansion_k"])
    min_overlap = tb.seconds_to_ns(float(cfg["synchronization"]["min_overlap_s"]))
    min_frac = float(cfg["synchronization"].get("min_overlap_fraction", 0.5))

    win_by_event: Dict[str, List[Tuple[str, int, int]]] = {}
    for _, w in windows.iterrows():
        win_by_event.setdefault(w["event_id"], []).append(
            (w["window_id"], int(w["w_start_utc_ns"]), int(w["w_end_utc_ns"])))

    sigma_by_source = dict(zip(sources["source_id"], sources["clock_sigma_ms"]))

    assigned: List[str | None] = []
    diags: List[dict] = []
    for _, o in observations.iterrows():
        sigma_ms = float(sigma_by_source.get(o["source_id"], 0.0))
        half = tb.seconds_to_ns(k * sigma_ms / 1000.0)
        lo, hi = tb.expand(int(o["obs_start_utc_ns"]), int(o["obs_end_utc_ns"]), half)

        best, best_ov, second_ov, best_span = None, 0, 0, 0
        for (wid, a, b) in win_by_event.get(o["event_id"], []):
            ov = tb.overlap_ns((lo, hi), (a, b))
            if ov > best_ov:
                best, second_ov, best_ov = wid, best_ov, ov
                best_span = min(hi - lo, b - a)
            elif ov > second_ov:
                second_ov = ov

        # Either criterion suffices. The absolute one governs long observations,
        # where a second of common support is a meaningful amount of evidence;
        # the fractional one governs short ones, where the whole observation is
        # shorter than the absolute threshold and only containment is meaningful.
        ok = best is not None and (
            best_ov >= min_overlap
            or (best_span > 0 and best_ov / best_span >= min_frac))
        assigned.append(best if ok else None)
        diags.append({
            "observation_id": o["observation_id"],
            "event_id": o["event_id"],
            "stream": o["stream"],
            "modality": o["modality"],
            "expansion_half_width_s": half / tb.NS,
            "best_overlap_s": best_ov / tb.NS,
            "runner_up_overlap_s": second_ov / tb.NS,
            "decisiveness": (best_ov - second_ov) / best_ov if best_ov else 0.0,
            "associated": bool(ok),
            "coverage_fraction": (best_ov / best_span) if best_span else 0.0,
            "reason": ("associated" if ok
                       else ("no_window_overlap" if best_ov == 0
                             else "overlap_below_minimum")),
        })

    out = observations.copy()
    out["window_id"] = assigned
    return out, pd.DataFrame(diags)


def load_sync_markers(path, salt, cfg, t0_ns) -> pd.DataFrame:
    """Read the marker log and compute Equation (3) per source and event.

    A marker is one physical instant that several disciplined sources observe at
    once, so the deviation between what a source recorded and the reference is a
    clock error and nothing else. This is what Equation (3) means; measuring the
    gap between an arbitrary observation and the event anchor instead would
    report where in the event the observation happened to fall.
    """
    import json
    from .ingest.common import rotation_epoch
    rot = int(cfg.release["rotation_policy_days"])
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            true_ns = tb.rfc3339_to_ns(rec["true_marker_utc"])
            obs_ns = tb.rfc3339_to_ns(rec["observed_marker_utc"])
            epoch = rotation_epoch(true_ns, t0_ns, rot)
            rows.append({
                "native_run_id": rec["native_run_id"],
                "source_id": ids.rotating_source_id(salt, rec["source_key"], epoch),
                "sync_method": rec["sync_method"],
                "declared_sigma_ms": float(rec["declared_sigma_ms"]),
                "sync_error_ns": int(abs(obs_ns - true_ns)),
            })
    return pd.DataFrame(rows)


def compute_sync_error(observations: pd.DataFrame, markers: pd.DataFrame,
                       run_to_event: Dict[str, str]) -> pd.DataFrame:
    """Attach the measured Equation (3) error to every observation.

    The error belongs to a (source, event) pair, not to an individual record: one
    clock offset governs everything that source produced during that run. Sources
    that cannot observe the marker - mobile devices and the external public feed -
    keep a null error, which the report renders as "not measurable" rather than
    as zero.
    """
    out = observations.copy()
    out["sync_error_ns"] = pd.NA
    if markers is None or markers.empty:
        return out
    m = markers.copy()
    m["event_id"] = m["native_run_id"].map(run_to_event)
    m = m.dropna(subset=["event_id"])
    lookup = {(r.event_id, r.source_id): int(r.sync_error_ns)
              for r in m.itertuples()}
    out["sync_error_ns"] = [
        lookup.get((e, s)) for e, s in zip(out["event_id"], out["source_id"])]
    return out


def sync_report(observations: pd.DataFrame, sources: pd.DataFrame,
                cfg: Config) -> pd.DataFrame:
    """Median / p95 / max of Eq. (3) by modality, with the tolerance-exceedance rate.

    Modalities whose sources cannot observe a marker appear with n = 0 and a
    declared uncertainty instead of a measured error. Reporting a measured
    statistic for them would be fabrication; omitting them entirely would hide
    that a third of the corpus has no verified synchronization at all.
    """
    tol_ns = tb.seconds_to_ns(float(cfg["synchronization"]["sync_tolerance_ms"]) / 1000.0)
    sigma = dict(zip(sources["source_id"], sources["clock_sigma_ms"])) \
        if sources is not None and not sources.empty else {}
    rows: List[dict] = []
    for modality, grp in observations.groupby("modality"):
        e = grp["sync_error_ns"].dropna().astype("int64")
        s = tb.sync_summary(e.tolist())
        s["modality"] = modality
        s["over_tolerance_rate"] = float((e > tol_ns).mean()) if len(e) else float("nan")
        s["n_not_measurable"] = int(grp["sync_error_ns"].isna().sum())
        s["declared_sigma_ms"] = float(np.mean(
            [sigma.get(x, np.nan) for x in grp["source_id"]])) if len(grp) else np.nan
        rows.append(s)
    e = observations["sync_error_ns"].dropna().astype("int64")
    allrow = tb.sync_summary(e.tolist())
    allrow["modality"] = "ALL"
    allrow["over_tolerance_rate"] = float((e > tol_ns).mean()) if len(e) else float("nan")
    allrow["n_not_measurable"] = int(observations["sync_error_ns"].isna().sum())
    allrow["declared_sigma_ms"] = float(np.nanmean(list(sigma.values()))) if sigma else np.nan
    rows.append(allrow)
    cols = ["modality", "n", "n_not_measurable", "median_ms", "p95_ms", "max_ms",
            "mean_ms", "over_tolerance_rate", "declared_sigma_ms"]
    return pd.DataFrame(rows)[cols]
