"""Repository packaging: RO-Crate, DataCite, PROV-O, and the integrity manifest.

The package is what makes the release citable and re-executable rather than a
folder of files. Three vocabularies are used, each for what it is good at:

* **RO-Crate** (JSON-LD) connects the data objects, the code, the people, and the
  licences inside one machine-readable manifest.
* **DataCite** carries the citation metadata a repository needs to mint and
  resolve a DOI.
* **PROV-O** records what was done to each object, by which software version,
  with which parameters, and with what result.

Fields that a real deposit must supply - the DOI, the licence, the publisher -
are emitted as explicit nulls with a ``requires_completion`` list rather than
being filled with plausible placeholders. A package that silently invents its own
licence is worse than one that admits it has none.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd

from . import ids, schema, timebase as tb
from .config import Config

PROV_CONTEXT = "http://www.w3.org/ns/prov#"


def ro_crate_metadata(cfg: Config, files: List[dict], counts: Dict[str, int],
                      provenance_ref: str = "metadata/provenance.jsonl") -> dict:
    rel = cfg.release
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entities: List[dict] = [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork",
         "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
         "about": {"@id": "./"}},
        {"@id": "./", "@type": "Dataset",
         "name": rel["dataset_title"],
         "version": rel["dataset_version"],
         "datePublished": now,
         "identifier": rel["doi"],
         "license": rel["open_tier_license"],
         "description": ("Event-centered multisource multimodal dataset for early "
                         "warning of approaching small unmanned aerial vehicles."),
         "hasPart": [{"@id": f["path"]} for f in files],
         "mentions": {"@id": provenance_ref},
         "measurementTechnique": [
             "authorized controlled flights with reference trajectory",
             "public warning feed ingestion",
             "voluntary mobile reports",
             "authorized site visual and acoustic recording"],
         "variableMeasured": sorted({t for t in schema.TABLES}),
         "size": counts},
    ]
    for f in files:
        entities.append({
            "@id": f["path"], "@type": "File",
            "encodingFormat": f.get("media_type", "application/octet-stream"),
            "contentSize": f.get("size_bytes"),
            "sha256": f.get("sha256"),
        })
    return {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": entities}


def datacite_metadata(cfg: Config) -> dict:
    """DataCite record with unresolved fields listed rather than invented."""
    rel = cfg.release
    missing = [k for k in ("doi", "open_tier_license") if not rel.get(k)]
    return {
        "types": {"resourceTypeGeneral": "Dataset", "resourceType": "Data Descriptor"},
        "titles": [{"title": rel["dataset_title"]}],
        "publisher": None,
        "publicationYear": datetime.now(timezone.utc).year,
        "version": rel["dataset_version"],
        "identifiers": [{"identifier": rel["doi"], "identifierType": "DOI"}]
        if rel["doi"] else [],
        "rightsList": [{"rights": rel["open_tier_license"]}]
        if rel["open_tier_license"] else [],
        "subjects": [{"subject": s} for s in (
            "small unmanned aerial vehicle", "multimodal dataset", "early warning",
            "spatiotemporal data", "acoustic sensing", "visual sensing",
            "data provenance", "technical validation")],
        "descriptions": [{"descriptionType": "TechnicalInfo",
                          "description": "Two access tiers: sanitized open tier and "
                                         "documented controlled-access tier."}],
        "requires_completion": missing,
    }


def provenance_records(cfg: Config, salt: bytes, activities: List[dict]) -> List[dict]:
    """PROV-O activity records, one per transformation the pipeline performed."""
    out: List[dict] = []
    for a in activities:
        aid = ids.activity_id(salt, a["activity"], a.get("subject", ""))
        out.append({
            "@type": f"{PROV_CONTEXT}Activity",
            "activity_id": aid,
            "activity": a["activity"],
            "startedAtTime": a.get("started"),
            "endedAtTime": a.get("ended"),
            "wasAssociatedWith": a.get("agent", "uavews.cli"),
            "software_version": a.get("software_version"),
            "parameter_file": str(cfg.source_path.name),
            "used": a.get("used", []),
            "generated": a.get("generated", []),
            "status": a.get("status", "succeeded"),
            "note": a.get("note"),
        })
    return out


def write_checksums(root: Path, out_path: Path,
                    skip: tuple[str, ...] = (".git", "__pycache__")) -> pd.DataFrame:
    """Digest every released file and write the integrity manifest.

    The manifest covers the exact byte sequence of every file in the package,
    including the metadata files - so a later alteration of the crate manifest
    itself is detectable, not just an alteration of the data.
    """
    rows: List[dict] = []
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if any(part in skip for part in p.parts) or rel == out_path.name:
            continue
        rows.append({"path": rel, "sha256": ids.sha256_file(p),
                     "size_bytes": p.stat().st_size})
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for _, r in df.iterrows():
            fh.write(f"{r['sha256']}  {r['path']}\n")
    return df


def release_metadata(cfg: Config, counts: Dict[str, object],
                     coverage: Dict[str, object]) -> dict:
    rel = cfg.release
    return {
        "dataset_title": rel["dataset_title"],
        "dataset_version": rel["dataset_version"],
        "doi": rel["doi"],
        "open_tier_license": rel["open_tier_license"],
        "controlled_tier_terms": rel["controlled_tier_terms"],
        "coordinate_generalization": {
            "public_spatial_resolution_m": rel["public_spatial_resolution_m"],
            "method": "floor-truncation to a metric cell in a local frame; "
                      "the frame origin is controlled-tier information",
        },
        "clocks": cfg["synchronization"],
        "controlled_vocabularies": {k: v for k, v in cfg.vocab.items()},
        "kinematic_parameters": {
            "delta_t_s": cfg.delta_t_s,
            "epsilon_m": cfg.epsilon_m,
            "epsilon_floor_m": cfg.epsilon_floor_m,
            "epsilon_derivation": "k * sqrt(2) * sigma_h",
        },
        "counts": counts,
        "coverage": coverage,
        "semantic_versioning": {
            "major": "schema or label meaning changes",
            "minor": "backward-compatible records or fields added",
            "patch": "metadata or file-level repair, no scientific change",
        },
        "provenance_note": ("Values in this file are computed by uavews.cli from "
                            "the ingested release. They are not transcribed from "
                            "any manuscript."),
    }


def write_package(out_root: Path, tables: Dict[str, pd.DataFrame],
                  manifests: Dict[str, pd.DataFrame], cfg: Config, salt: bytes,
                  activities: List[dict], reports: Dict[str, object]) -> Dict[str, Path]:
    """Assemble the deposit-shaped package on disk."""
    out_root = Path(out_root)
    (out_root / "tables").mkdir(parents=True, exist_ok=True)
    (out_root / "metadata").mkdir(parents=True, exist_ok=True)
    (out_root / "splits").mkdir(parents=True, exist_ok=True)
    (out_root / "docs").mkdir(parents=True, exist_ok=True)
    (out_root / "report").mkdir(parents=True, exist_ok=True)

    written: Dict[str, Path] = {}
    file_entries: List[dict] = []

    for name, df in tables.items():
        if df is None:
            continue
        p = out_root / "tables" / f"{name}.parquet"
        try:
            df.to_parquet(p, index=False)
            media_type = "application/vnd.apache.parquet"
        except Exception:
            p = p.with_suffix(".csv")
            df.to_csv(p, index=False)
            media_type = "text/csv"
        written[name] = p
        file_entries.append({"path": p.relative_to(out_root).as_posix(),
                             "media_type": media_type,
                             "size_bytes": p.stat().st_size,
                             "sha256": ids.sha256_file(p)})

    for name, man in manifests.items():
        p = out_root / "splits" / f"{name}.csv"
        man.to_csv(p, index=False)
        written[f"split:{name}"] = p
        file_entries.append({"path": p.relative_to(out_root).as_posix(),
                             "media_type": "text/csv",
                             "size_bytes": p.stat().st_size,
                             "sha256": ids.sha256_file(p)})

    dd = out_root / "docs" / "data_dictionary.csv"
    schema.data_dictionary().to_csv(dd, index=False)
    written["data_dictionary"] = dd
    file_entries.append({"path": dd.relative_to(out_root).as_posix(),
                         "media_type": "text/csv",
                         "size_bytes": dd.stat().st_size,
                         "sha256": ids.sha256_file(dd)})

    counts = {k: int(len(v)) for k, v in tables.items() if v is not None}
    coverage = reports.get("coverage", {})

    rm = out_root / "metadata" / "release_metadata.json"
    rm.write_text(json.dumps(release_metadata(cfg, counts, coverage), indent=2,
                             default=str), encoding="utf-8")
    written["release_metadata"] = rm

    prov = out_root / "metadata" / "provenance.jsonl"
    with open(prov, "w", encoding="utf-8") as fh:
        for rec in provenance_records(cfg, salt, activities):
            fh.write(json.dumps(rec, default=str) + "\n")
    written["provenance"] = prov

    dc = out_root / "metadata" / "datacite.json"
    dc.write_text(json.dumps(datacite_metadata(cfg), indent=2), encoding="utf-8")
    written["datacite"] = dc

    crate = out_root / "ro-crate-metadata.json"
    crate.write_text(json.dumps(
        ro_crate_metadata(cfg, file_entries, counts), indent=2, default=str),
        encoding="utf-8")
    written["ro_crate"] = crate

    chk = out_root / "checksums_sha256.txt"
    write_checksums(out_root, chk)
    written["checksums"] = chk
    return written
