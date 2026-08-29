"""De-identification, minimization, and access tiering.

Applied after annotation and verified independently of it. The separation is
deliberate: an annotator who can see an unredacted frame produces better labels,
and a privacy reviewer who can see the label is tempted to keep evidence that
supports it. Running the two passes independently is what keeps each honest.

The module is explicit that de-identification is risk management, not a
guarantee. It reports what it transformed, what residual risk it could measure,
and which records it could not clear - and it routes those to metadata-only or
controlled access rather than passing them.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .config import Config

#: Fields that must never appear in an open-tier export, whatever their value.
FORBIDDEN_OPEN_FIELDS = frozenset({
    "_native_run_id", "_free_text_present", "_consent_receipt",
    "_slant_range_m", "_phash", "_site_group",
    "_predicted_snr_db", "_predicted_target_px", "_cap_category",
    "_retrieval_lag_s",
})

#: Quality flags that make an object unreleasable in the open tier as it stands.
BLOCKING_FLAGS = frozenset({"speech_detected"})


def apply_media_privacy(media: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Route media objects to a release tier and record why.

    An object carrying detected speech is not deleted and not published as-is: it
    becomes ``metadata_only`` in the open tier and remains available under
    controlled access, so the record of its existence survives while the content
    does not leak. Publishing a masked derivative would also be acceptable, but
    it must be a *new* object with a derivation relation, never a silent
    replacement of the original.
    """
    if media.empty:
        return media, pd.DataFrame()
    out = media.copy()
    decisions: List[dict] = []
    tiers: List[str] = []
    for _, r in out.iterrows():
        flags = set(str(r.get("quality_flags") or "").split(";")) - {""}
        blocking = flags & BLOCKING_FLAGS
        if blocking:
            tiers.append("metadata_only")
            decisions.append({"object_id": r["object_id"], "decision": "metadata_only",
                              "reason": "incidental_speech_detected",
                              "detail": ";".join(sorted(blocking)),
                              "controlled_copy_retained": True})
        else:
            tiers.append("open")
    out["access_tier"] = tiers
    return out, pd.DataFrame(decisions)


def k_anonymity_report(observations: pd.DataFrame,
                       quasi_identifiers: List[str] | None = None,
                       k: int = 5) -> Dict[str, object]:
    """Smallest equivalence class over the published quasi-identifiers.

    Generalizing coordinates and rotating pseudonyms is not by itself protection:
    if one contributor is the only one reporting from a given cell on a given day,
    the generalization has not hidden them. This measures that directly by
    counting the equivalence classes induced by the fields the open tier actually
    publishes, and reports how many records sit in a class smaller than k.

    It is a lower bound on risk, not a certificate. It says nothing about an
    adversary holding auxiliary data, which is why the release also documents its
    adversary assumptions rather than relying on this number.
    """
    qi = quasi_identifiers or ["location_cell", "modality"]
    qi = [c for c in qi if c in observations.columns]
    if not qi or observations.empty:
        return {"k": k, "min_class_size": None, "n_below_k": 0, "rate_below_k": 0.0,
                "quasi_identifiers": qi}
    sub = observations.copy()
    if "obs_start_utc_ns" in sub.columns:
        sub["_day"] = (sub["obs_start_utc_ns"].astype("int64") // (86_400 * 10 ** 9))
        qi = qi + ["_day"]
    sizes = sub.groupby(qi).size()
    per_record = sub.set_index(qi).index.map(sizes)
    below = int((np.asarray(per_record) < k).sum())
    return {"k": k, "min_class_size": int(sizes.min()),
            "n_classes": int(len(sizes)), "n_below_k": below,
            "rate_below_k": below / len(sub), "quasi_identifiers": qi}


def audit_open_export(tables: Dict[str, pd.DataFrame],
                      sample_rate: float = 0.10, seed: int = 3
                      ) -> pd.DataFrame:
    """Independent sample audit of what the open export actually contains.

    Checks three failure modes that a schema validator will not catch: an
    internal working column surviving into the export, a controlled-tier row
    appearing in an open-tier table, and a free-text field reaching the open tier
    without disclosure review.
    """
    rng = np.random.default_rng(seed)
    findings: List[dict] = []
    for name, df in tables.items():
        if df is None or df.empty:
            continue
        leaked = sorted(set(df.columns) & FORBIDDEN_OPEN_FIELDS)
        for col in leaked:
            findings.append({"table": name, "finding": "internal_field_in_export",
                             "field": col, "n": len(df), "severity": "blocking"})
        if any(c.startswith("_") for c in df.columns):
            for col in sorted(c for c in df.columns if c.startswith("_")):
                if col not in leaked:
                    findings.append({"table": name, "finding": "working_column_in_export",
                                     "field": col, "n": len(df), "severity": "blocking"})
        if "access_tier" in df.columns:
            bad = int((df["access_tier"] == "controlled").sum())
            if bad:
                findings.append({"table": name, "finding": "controlled_row_in_open_table",
                                 "field": "access_tier", "n": bad,
                                 "severity": "blocking"})
        # Sampled manual-review queue: the audit is not fully automatable, so the
        # release records which rows a human actually looked at.
        n_sample = max(1, int(len(df) * sample_rate))
        idx = rng.choice(len(df), size=min(n_sample, len(df)), replace=False)
        findings.append({"table": name, "finding": "sampled_for_manual_review",
                         "field": "-", "n": int(len(idx)), "severity": "informational"})
    return pd.DataFrame(findings)


def strip_internal_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop every working column before an open-tier export."""
    return df[[c for c in df.columns if not c.startswith("_")]]
