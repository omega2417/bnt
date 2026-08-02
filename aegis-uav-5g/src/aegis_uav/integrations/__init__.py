"""Level-2 external-validity adapters (future work).

The Level-1 MVP in this repository is a fully reproducible synthetic evaluation.
Level-2 integrations strengthen external validity by driving the same feature
and agent interfaces from higher-fidelity sources:

- ``px4_gazebo``   — PX4 SITL + Gazebo flight dynamics / MAVLink telemetry.
- ``ns3_5glena``   — ns-3 + 5G-LENA network traces (flow/routing features).
- ``mininet_sdn``  — Mininet/Containernet SDN enforcement backend for the PEA.

These adapters are intentionally out of scope for the current publication, which
reports Level-1 results explicitly labelled as synthetic evaluation.  They are
declared here so the interface boundary is explicit and stable.
"""
