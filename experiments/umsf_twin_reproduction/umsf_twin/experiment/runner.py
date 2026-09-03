"""Single-run driver: assembles the federation, runs it, writes the artifacts.

This is the function every other entry point goes through - the CLI, the DoE
sweep, the Monte Carlo driver and the tests - so that a run produced by any of
them carries the same manifest, the same gates and the same directory layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import __version__
from ..core.bus import EventBus
from ..core.clock import SimClock
from ..core.contracts import ALERT_FIELDS, GROUND_TRUTH_FIELDS, TELEMETRY_FIELDS
from ..core.events import EventIndex
from ..core.orchestrator import Orchestrator
from ..core.provenance import RunManifest, canonical_hash, source_tree_hash
from ..core.rng import RngHub
from ..federates.assets.federate import AssetFederate
from ..federates.detection.federate import DetectionFederate
from ..federates.network.federate import NetworkFederate
from ..federates.power.federate import PowerFederate
from ..federates.response.federate import ResponseFederate
from ..federates.telemetry.federate import TelemetryFederate
from ..federates.threats.federate import ThreatFederate
from ..federates.truth.federate import GroundTruthFederate
from ..federates.wifi.federate import WifiFederate
from ..federates.workload.federate import WorkloadFederate
from ..pipelines.export import ensure_run_dir, write_csv, write_json
from ..pipelines.labeling import label_rows
from ..pipelines.validation import DEFAULT_GATES, run_gates, step_invariants
from .metrics import summarize
from .scenario import Scenario

__all__ = ["build_federation", "run_replicate", "run_experiment"]


def build_federation(scenario: Scenario, replicate_id: int, run_id: str
                     ) -> tuple[Orchestrator, dict[str, Any]]:
    """Instantiate every federate for one replicate."""

    config = scenario.config
    clock = SimClock.from_iso(str(config["start_utc"]), scenario.dt_s)
    rng = RngHub(scenario.seed, replicate_id)
    events = EventIndex(list(scenario.events))
    sites = list(config["sites"])

    power = PowerFederate(config["power"]["site_a"], events, rng)
    assets = AssetFederate(config["sites"], events, rng)
    workload = WorkloadFederate(config["sites"], events, rng)
    threats = ThreatFederate(config["sites"], events, rng)
    network = NetworkFederate(config["sites"], config.get("vpn", {}), events, rng)
    wifi = WifiFederate(config["sites"], events, rng)
    telemetry = TelemetryFederate(
        sites, events, rng, run_id, replicate_id, mode=scenario.policy.mode,
        evidence_class=str(config.get("evidence_class", "synthetic_demo")),
        defects_enabled=bool(config.get("telemetry", {}).get("defects_enabled", True)),
    )
    detector_cfg = config.get("detector", {})
    detection = DetectionFederate(
        sites, rng, threshold=float(detector_cfg.get("threshold", 0.35)),
        arms=tuple(detector_cfg.get("arms", ("rules", "edge", "edge_correlated"))),
    )
    response = ResponseFederate(shadow_mode=bool(detector_cfg.get("shadow_mode", True)))
    truth = GroundTruthFederate(events, run_id, replicate_id, str(config["start_utc"]))

    orchestrator = Orchestrator(clock, scenario.policy, scenario.registry, EventBus())
    orchestrator.add(power, assets, workload, threats, network, wifi,
                     telemetry, detection, response, truth)
    orchestrator.add_invariant(step_invariants)
    orchestrator.initialize()
    components = {"power": power, "assets": assets, "workload": workload,
                  "threats": threats, "network": network, "wifi": wifi,
                  "telemetry": telemetry, "detection": detection,
                  "response": response, "truth": truth}
    return orchestrator, components


def run_replicate(scenario: Scenario, replicate_id: int, run_id: str) -> dict[str, Any]:
    """Run one replicate in memory and return its artifacts."""

    orchestrator, parts = build_federation(scenario, replicate_id, run_id)
    telemetry: TelemetryFederate = parts["telemetry"]
    detection: DetectionFederate = parts["detection"]
    response: ResponseFederate = parts["response"]
    truth: GroundTruthFederate = parts["truth"]

    detector_scores: list[dict[str, Any]] = []
    for _ in orchestrator.run(scenario.duration_s):
        shared = orchestrator.context["shared"]
        for site_id, row in shared.get("detection", {}).items():
            detector_scores.append({"site_id": site_id,
                                    "step": orchestrator.clock.step_index - 1,
                                    "score": row.get("score"),
                                    "alert": row.get("alert")})

    # Detector output is joined back onto the delivered telemetry rows; gap
    # rows keep empty detector fields, exactly as the contract requires.
    scores = {(item["site_id"], item["step"]): item for item in detector_scores}
    for row in telemetry.rows:
        key = (row["site_id"], int(row["step"]))
        item = scores.get(key)
        if item and item["score"] is not None and row.get("telemetry_gap_marker") != 1:
            row["detector_score"] = round(float(item["score"]), 5)
            row["detector_alert"] = int(bool(item["alert"]))

    truth_rows = truth.all_truth(scenario.dt_s)
    labeled = label_rows(telemetry.rows, truth_rows)
    return {
        "rows": telemetry.rows,
        "truth": truth_rows,
        "labeled": labeled,
        "alerts": detection.alerts,
        "response_audit": response.audit,
        "health": orchestrator.health(),
        "checkpoint": orchestrator.checkpoint(),
        "transitions": len(truth.transitions),
    }


def run_experiment(scenario: Scenario, output_root: str | Path, replicates: int = 1,
                   run_id: str | None = None, write_artifacts: bool = True
                   ) -> dict[str, Any]:
    """Run ``replicates`` replicates and publish a complete run directory."""

    run_id = run_id or f"{scenario.experiment_id}-{scenario.config_hash[:8]}"
    scenario.policy.check_budget(scenario.duration_s, len(scenario.events), replicates)

    all_rows: list[dict[str, Any]] = []
    all_truth: list[dict[str, Any]] = []
    all_alerts: list[dict[str, Any]] = []
    all_audit: list[dict[str, Any]] = []
    per_replicate: list[dict[str, Any]] = []
    sites = list(scenario.config["sites"])

    for replicate_id in range(replicates):
        result = run_replicate(scenario, replicate_id, run_id)
        all_rows.extend(result["rows"])
        all_truth.extend(result["truth"])
        all_alerts.extend(result["alerts"])
        all_audit.extend(result["response_audit"])
        per_replicate.append({
            "replicate_id": replicate_id,
            "rows": len(result["rows"]),
            "alerts": len(result["alerts"]),
            "transitions": result["transitions"],
            "summary": summarize(result["rows"], result["labeled"], sites),
        })

    labeled = label_rows(all_rows, all_truth)
    gates = run_gates(all_rows, DEFAULT_GATES)
    summary = {
        "run_id": run_id,
        "experiment_id": scenario.experiment_id,
        "mode": scenario.policy.mode,
        "evidence_class": scenario.config.get("evidence_class", "synthetic_demo"),
        "replicates": replicates,
        "duration_s": scenario.duration_s,
        "dt_s": scenario.dt_s,
        "config_hash": scenario.config_hash,
        "aggregate": summarize(all_rows, labeled, sites),
        "per_replicate": per_replicate,
        "gates": gates,
        "invariant_notes": list(scenario.invariant_notes),
        "claim_boundary": ("Synthetic model output. Not a measurement of the physical "
                           "UMSF cyber range and not a safety authorisation."),
    }

    if not write_artifacts:
        return {"summary": summary, "rows": all_rows, "truth": all_truth,
                "alerts": all_alerts}

    run_dir = ensure_run_dir(output_root, run_id)
    manifest = RunManifest(run_id, scenario.experiment_id, scenario.policy.mode,
                           scenario.seed, __version__)
    manifest.set_policy(scenario.policy.to_dict())
    manifest.set_parameters(scenario.registry.evidence_histogram(),
                            scenario.registry.unknowns())
    manifest.set_gates(gates)
    manifest.set_hash("config", scenario.config_hash)
    manifest.set_hash("engine_source", source_tree_hash(Path(__file__).resolve().parents[1]))
    manifest.set_hash("summary", canonical_hash(summary))
    for note in scenario.invariant_notes:
        manifest.note(note)

    paths = [
        write_csv(run_dir / "telemetry.csv", all_rows, TELEMETRY_FIELDS),
        write_csv(run_dir / "ground_truth.csv", all_truth, GROUND_TRUTH_FIELDS),
        write_csv(run_dir / "alerts.csv", all_alerts, ALERT_FIELDS),
        write_json(run_dir / "response_audit.json", all_audit),
        write_json(run_dir / "parameters.json", scenario.registry.table()),
        write_json(run_dir / "scenario.resolved.json", scenario.materialized()),
        write_json(run_dir / "summary.json", summary),
    ]
    for path in paths:
        manifest.add_artifact(path)
    manifest_path = manifest.finalize(run_dir / "manifest.json")
    return {"summary": summary, "run_dir": str(run_dir),
            "manifest": str(manifest_path), "artifacts": [str(p) for p in paths]}
