"""End-to-end demo: rogue-AP incident -> SAR + SOC decision (prompt M23.20).

Run::

    python examples/demo_rogue_ap.py
"""

from __future__ import annotations

import json

from awa.api import build_environment, run_incident
from awa.digital_twin.twin import Scenario


def main() -> None:
    env = build_environment(seed=1)
    # A source in the CRITICAL zone (server room), plus an injected rogue AP.
    ctx = run_incident(
        env, true_xy=(33.0, 12.0), incident_id="INC-ROGUE-0001",
        scenario=Scenario.ROGUE_AP, seed=777,
    )

    print("=" * 70)
    print("AGENT AUDIT TRAIL")
    print("=" * 70)
    for e in ctx.audit_log:
        print(f"  [{e['agent']:>22}] {e['message']}")

    print("\n" + "=" * 70)
    print("LOCALISATION")
    print("=" * 70)
    u = ctx.uncertainty
    print(f"  MAP coordinate       : {[round(v, 2) for v in u['MAP']]}")
    print(f"  HPD area (95%)       : {u['HPD_area_m2']:.1f} m^2")
    print(f"  entropy (nats)       : {u['entropy_nats']:.3f}")
    print(f"  spatial modes        : {u['multimodality_modes']}")
    print(f"  zone posterior       : "
          f"{ {k: round(v, 3) for k, v in u['zone_posterior'].items()} }")

    print("\n" + "=" * 70)
    print("DRIFT / CONSISTENCY / THREAT")
    print("=" * 70)
    print(f"  drift_state          : {ctx.drift_state}")
    print(f"  consistency          : {ctx.consistency}")
    print(f"  threat_state         : {ctx.threat_state}")

    print("\n" + "=" * 70)
    print("SOC DECISION")
    print("=" * 70)
    print(f"  {ctx.decision}")

    print("\n" + "=" * 70)
    print("SPATIAL ATTRIBUTION RECORD (SAR)")
    print("=" * 70)
    print(json.dumps(ctx.sar, indent=2)[:1500] + "\n  ...")

    print(f"\n  provenance_hash: {ctx.sar['provenance_hash']}")


if __name__ == "__main__":
    main()
