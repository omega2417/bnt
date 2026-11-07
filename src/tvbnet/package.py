"""Stage P: canonical Parquet tables, manifests, data dictionary, DataCite, object-level PROV-O, RO-Crate, checksums."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import pandas as pd

from .validate import SCHEMA

DESCR = {
    "scenarios": "One row per synthetic scenario: design factors, structural sizes, baseline risk, budget",
    "networks": "Network configuration summary per scenario", "nodes": "Network nodes", "links": "Network links",
    "assets": "Information assets with technical/economic/security indicators, reliability and value",
    "vulnerabilities": "Asset vulnerabilities with exploitability and threat-class mask",
    "threats": "Threats with class, origin, annual rate, severity and reliability-perturbed estimates",
    "barriers": "Candidate protective barriers: layer, tier, effectiveness, annual cost, scope, estimates",
    "configurations": "Selected protective configurations per method and derived indicators",
    "frontier": "Cost-risk Pareto frontier points (exhaustive enumeration)",
}


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_package(out: str, tables: dict, manifests: dict, cfg: dict, prov_activities: list) -> dict:
    os.makedirs(f"{out}/tables", exist_ok=True); os.makedirs(f"{out}/splits", exist_ok=True)
    os.makedirs(f"{out}/metadata", exist_ok=True); os.makedirs(f"{out}/docs", exist_ok=True)
    files = {}
    for t, df in tables.items():
        pk = SCHEMA[t][0]
        df = df.sort_values(list(pk) if isinstance(pk, tuple) else pk).reset_index(drop=True)
        p = f"{out}/tables/{t}.parquet"; df.to_parquet(p, index=False); files[p] = len(df)
    for name, m in manifests.items():
        p = f"{out}/splits/{name}.csv"; m.sort_values("scenario_id").to_csv(p, index=False); files[p] = len(m)
    dd = []
    for t, (pk, cols, fks) in SCHEMA.items():
        for c in tables[t].columns:
            spec = cols.get(c)
            dd.append({"table": t, "column": c, "dtype": str(tables[t][c].dtype),
                       "required": bool(spec and spec[1]), "range": "" if not spec or not spec[2] else str(spec[2]),
                       "primary_key": c in (pk if isinstance(pk, tuple) else (pk,)),
                       "foreign_key": fks.get(c, ""), "table_description": DESCR[t]})
    pd.DataFrame(dd).to_csv(f"{out}/docs/data_dictionary.csv", index=False)
    now = datetime.now(timezone.utc).isoformat()
    datacite = {"titles": [{"title": "tvbnet 0.1.0-rehearsal: synthetic dataset for multilayer security and cost-risk trade-offs in data transmission networks"}],
                "types": {"resourceTypeGeneral": "Dataset"}, "version": cfg["release"],
                "rightsList": [{"rights": "CC BY 4.0"}], "publicationYear": 2026,
                "descriptions": [{"descriptionType": "Other", "description": "SYNTHETIC: all records are generated from a fixed seed; no operational measurement."}],
                "relatedIdentifiers": [{"relationType": "IsDerivedFrom", "relatedIdentifierType": "DOI", "relatedIdentifier": "10.5281/zenodo.22166893"},
                                       {"relationType": "References", "relatedIdentifierType": "DOI", "relatedIdentifier": "10.3390/data11090247"}]}
    json.dump(datacite, open(f"{out}/metadata/datacite.json", "w"), indent=2)
    # object-level PROV-O: every activity lists used and generated entities with digests
    ent = {}
    for p in files:
        ent[p] = {"@id": os.path.relpath(p, out), "@type": "prov:Entity", "sha256": sha256_file(p), "records": files[p]}
    graph = []
    for a in prov_activities:
        graph.append({"@id": f"activity:{a['name']}", "@type": "prov:Activity", "prov:startedAtTime": a["start"],
                      "prov:endedAtTime": a["end"], "prov:used": a["used"], "prov:generated": a["generated"],
                      "prov:wasAssociatedWith": f"software:tvbnet/{cfg['release']}", "parameters": "config/pipeline.yaml"})
    prov = {"@context": {"prov": "http://www.w3.org/ns/prov#"}, "@graph": graph + list(ent.values())}
    json.dump(prov, open(f"{out}/metadata/provenance.jsonld", "w"), indent=2)
    crate = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": [
        {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"}, "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}},
        {"@id": "./", "@type": "Dataset", "name": datacite["titles"][0]["title"], "datePublished": now[:10],
         "license": "https://creativecommons.org/licenses/by/4.0/", "hasPart": [{"@id": e["@id"]} for e in ent.values()]},
        *[{"@id": e["@id"], "@type": "File", "contentSize": os.path.getsize(p), "sha256": e["sha256"]} for p, e in ent.items()]]}
    json.dump(crate, open(f"{out}/ro-crate-metadata.json", "w"), indent=2)
    lines = []
    for root, _, fs in os.walk(out):
        for f in sorted(fs):
            p = os.path.join(root, f)
            if f != "checksums_sha256.txt":
                lines.append(f"{sha256_file(p)}  {os.path.relpath(p, out)}")
    open(f"{out}/checksums_sha256.txt", "w").write("\n".join(sorted(lines, key=lambda s: s[66:])) + "\n")
    return {"files": {os.path.relpath(k, out): v for k, v in files.items()}, "n_checksummed": len(lines)}


def verify_checksums(out: str) -> float:
    ok = n = 0
    for line in open(f"{out}/checksums_sha256.txt"):
        d, p = line.strip().split("  ", 1)
        n += 1; ok += int(sha256_file(os.path.join(out, p)) == d)
    return ok / n if n else 0.0
