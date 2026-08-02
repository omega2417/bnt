"""Network-modality raw signal generator (flow- and routing-level features)."""

from __future__ import annotations

import numpy as np

from ..rng import SeededRng
from ..schemas import ScenarioConfig

__all__ = ["simulate_network"]


def simulate_network(
    scenario: ScenarioConfig, n_steps: int, rng: SeededRng
) -> dict[str, np.ndarray]:
    n = scenario.fleet_size
    net = scenario.network
    gen = rng.generator

    pps = np.clip(gen.normal(net.base_packets_per_s, 6.0, size=(n, n_steps)), 1, None)
    bpp = np.clip(gen.normal(net.base_bytes_per_packet, 25.0, size=(n, n_steps)), 40, None)
    packets_out = pps
    packets_in = np.clip(gen.normal(net.base_packets_per_s * 0.9, 6.0, size=(n, n_steps)), 1, None)
    bytes_out = packets_out * bpp
    bytes_in = packets_in * bpp

    flow_duration = np.clip(gen.normal(3.0, 0.8, size=(n, n_steps)), 0.1, None)
    active_flows = np.clip(gen.poisson(4, size=(n, n_steps)).astype(float), 1, None)
    dest_fanout = np.clip(gen.poisson(3, size=(n, n_steps)).astype(float), 1, None)
    src_fanout = np.clip(gen.poisson(2, size=(n, n_steps)).astype(float), 1, None)

    # Protocol mix as an integer code stream (entropy computed in features).
    protocol = gen.integers(0, 3, size=(n, n_steps))  # 0=telemetry,1=c2,2=video

    packet_loss = np.clip(gen.normal(net.base_packet_loss, 0.005, size=(n, n_steps)), 0, 1)
    retransmission = np.clip(gen.normal(0.02, 0.01, size=(n, n_steps)), 0, 1)
    rtt = np.clip(gen.normal(net.base_rtt_ms, 5.0, size=(n, n_steps)), 1, None)
    jitter = np.clip(gen.normal(net.base_jitter_ms, 1.5, size=(n, n_steps)), 0, None)

    route_changes = gen.poisson(0.2, size=(n, n_steps)).astype(float)
    routing_ctrl = np.clip(
        gen.normal(net.routing_control_rate, 0.5, size=(n, n_steps)), 0, None
    )
    neighbour_churn = np.clip(gen.normal(net.neighbour_churn, 0.02, size=(n, n_steps)), 0, None)
    failed_connections = gen.poisson(0.1, size=(n, n_steps)).astype(float)

    return {
        "packets_in": packets_in,
        "packets_out": packets_out,
        "bytes_in": bytes_in,
        "bytes_out": bytes_out,
        "packets_per_second": pps,
        "bytes_per_second": bytes_out + bytes_in,
        "mean_flow_duration": flow_duration,
        "active_flows": active_flows,
        "destination_fanout": dest_fanout,
        "source_fanout": src_fanout,
        "protocol_code": protocol.astype(float),
        "packet_loss": packet_loss,
        "retransmission_rate": retransmission,
        "rtt": rtt,
        "jitter": jitter,
        "route_changes": route_changes,
        "routing_control_rate": routing_ctrl,
        "neighbour_churn": neighbour_churn,
        "failed_connections": failed_connections,
    }
