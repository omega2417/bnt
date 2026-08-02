"""Windowed feature extraction for a single mission (vectorised).

Produces per-(uav, window) feature rows across three modalities plus derived and
cross-vehicle-consistency features.  Labels are assigned by majority vote over
the window's steps.  No standardisation happens here (that is fit on the train
split only, in :mod:`aegis_uav.features.pipeline`) to avoid leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from ..schemas import ScenarioConfig
from ..simulation.scenario_engine import MissionData

__all__ = ["mission_windows", "TELEMETRY_FEATURES", "NETWORK_FEATURES", "BEHAVIOUR_FEATURES",
           "CROSS_VEHICLE_FEATURES"]

TELEMETRY_FEATURES = [
    "tel_speed_mean", "tel_speed_std", "tel_accel_mean", "tel_roll_std", "tel_pitch_std",
    "tel_yaw_rate_std", "tel_altitude_mean", "tel_gnss_sat_mean", "tel_hdop_mean",
    "tel_vdop_mean", "tel_gnss_residual_mean", "tel_gnss_residual_max",
    "tel_gnss_disagreement_mean", "tel_gnss_disagreement_max", "tel_battery_mean",
    "tel_rssi_mean", "tel_sinr_mean",
]
NETWORK_FEATURES = [
    "net_pps_mean", "net_pps_std", "net_bps_mean", "net_flow_dur_mean", "net_active_flows_mean",
    "net_dest_fanout_mean", "net_dest_fanout_max", "net_src_fanout_mean", "net_src_fanout_max",
    "net_protocol_entropy", "net_packet_loss_mean", "net_packet_loss_max",
    "net_retransmission_mean", "net_rtt_mean", "net_rtt_max", "net_jitter_mean",
    "net_route_changes_sum", "net_routing_ctrl_mean", "net_neighbour_churn_mean",
    "net_failed_conn_sum",
]
BEHAVIOUR_FEATURES = [
    "beh_command_rate_mean", "beh_command_rate_std", "beh_command_type_entropy",
    "beh_unauth_cmd_sum", "beh_session_est_mean", "beh_session_term_mean",
    "beh_auth_fail_sum", "beh_credential_changes_sum", "beh_gcs_fanout_mean",
    "beh_gcs_fanout_max", "beh_unexpected_operator_max", "beh_unusual_seq_mean",
    "beh_unusual_seq_max", "beh_session_origin_change_max", "beh_priv_escalation_sum",
]
CROSS_VEHICLE_FEATURES = [
    "xv_gnss_disagreement_z", "xv_pps_z", "xv_command_rate_z", "xv_speed_z",
]

_XV_SOURCE = {
    "xv_gnss_disagreement_z": "tel_gnss_disagreement_mean",
    "xv_pps_z": "net_pps_mean",
    "xv_command_rate_z": "beh_command_rate_mean",
    "xv_speed_z": "tel_speed_mean",
}

# (output feature, source signal key, reduction op)
_AGG_SPEC: list[tuple[str, str, str]] = [
    ("tel_speed_mean", "speed", "mean"), ("tel_speed_std", "speed", "std"),
    ("tel_accel_mean", "accel", "mean"), ("tel_roll_std", "roll", "std"),
    ("tel_pitch_std", "pitch", "std"), ("tel_yaw_rate_std", "yaw_rate", "std"),
    ("tel_altitude_mean", "altitude", "mean"), ("tel_gnss_sat_mean", "gnss_sat", "mean"),
    ("tel_hdop_mean", "hdop", "mean"), ("tel_vdop_mean", "vdop", "mean"),
    ("tel_gnss_residual_mean", "gnss_residual", "mean"),
    ("tel_gnss_residual_max", "gnss_residual", "max"),
    ("tel_gnss_disagreement_mean", "disagreement", "mean"),
    ("tel_gnss_disagreement_max", "disagreement", "max"),
    ("tel_battery_mean", "battery", "mean"), ("tel_rssi_mean", "rssi", "mean"),
    ("tel_sinr_mean", "sinr", "mean"),
    ("net_pps_mean", "pps", "mean"), ("net_pps_std", "pps", "std"),
    ("net_bps_mean", "bps", "mean"), ("net_flow_dur_mean", "flow_dur", "mean"),
    ("net_active_flows_mean", "active_flows", "mean"),
    ("net_dest_fanout_mean", "dest_fanout", "mean"),
    ("net_dest_fanout_max", "dest_fanout", "max"),
    ("net_src_fanout_mean", "src_fanout", "mean"),
    ("net_src_fanout_max", "src_fanout", "max"),
    ("net_packet_loss_mean", "packet_loss", "mean"),
    ("net_packet_loss_max", "packet_loss", "max"),
    ("net_retransmission_mean", "retransmission", "mean"),
    ("net_rtt_mean", "rtt", "mean"), ("net_rtt_max", "rtt", "max"),
    ("net_jitter_mean", "jitter", "mean"), ("net_route_changes_sum", "route_changes", "sum"),
    ("net_routing_ctrl_mean", "routing_ctrl", "mean"),
    ("net_neighbour_churn_mean", "neighbour_churn", "mean"),
    ("net_failed_conn_sum", "failed_conn", "sum"),
    ("beh_command_rate_mean", "command_rate", "mean"),
    ("beh_command_rate_std", "command_rate", "std"),
    ("beh_unauth_cmd_sum", "unauth_cmd", "sum"),
    ("beh_session_est_mean", "session_est", "mean"),
    ("beh_session_term_mean", "session_term", "mean"),
    ("beh_auth_fail_sum", "auth_fail", "sum"),
    ("beh_credential_changes_sum", "cred_changes", "sum"),
    ("beh_gcs_fanout_mean", "gcs_fanout", "mean"),
    ("beh_gcs_fanout_max", "gcs_fanout", "max"),
    ("beh_unexpected_operator_max", "unexpected_operator", "max"),
    ("beh_unusual_seq_mean", "unusual_seq", "mean"),
    ("beh_unusual_seq_max", "unusual_seq", "max"),
    ("beh_session_origin_change_max", "session_origin_change", "max"),
    ("beh_priv_escalation_sum", "priv_escalation", "sum"),
]

_REDUCE = {
    "mean": lambda w: w.mean(axis=2),
    "std": lambda w: w.std(axis=2),
    "max": lambda w: w.max(axis=2),
    "sum": lambda w: w.sum(axis=2),
}


def _windows(a: np.ndarray, win: int, starts: np.ndarray) -> np.ndarray:
    """(n_uav, n_steps) -> (n_uav, n_windows, win)."""
    sw = sliding_window_view(a, win, axis=1)  # (n, n_steps-win+1, win)
    return sw[:, starts, :]


def _entropy_feature(codes: np.ndarray, win: int, starts: np.ndarray, k: int) -> np.ndarray:
    """Per-window Shannon entropy (base 2) of a categorical code stream."""
    w = _windows(codes, win, starts)  # (n, n_windows, win)
    n, nw, _ = w.shape
    ent = np.zeros((n, nw))
    for c in range(k):
        p = (w == c).mean(axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            term = np.where(p > 0, -p * np.log2(p), 0.0)
        ent += term
    return ent


def mission_windows(
    mission: MissionData,
    scenario: ScenarioConfig,
    window_length_s: float,
    stride_s: float,
) -> pd.DataFrame:
    frame = mission.frame
    n = scenario.fleet_size
    dt = scenario.export_period_s
    n_steps = int(round(scenario.mission_duration_s / dt))
    win = max(int(round(window_length_s / dt)), 1)
    stride = max(int(round(stride_s / dt)), 1)

    def R(col: str) -> np.ndarray:
        return frame[col].to_numpy().reshape(n, n_steps)

    px, py = R("position_x"), R("position_y")
    gx, gy = R("gnss_reported_x"), R("gnss_reported_y")
    disagreement = np.hypot(px - gx, py - gy)
    speed = np.sqrt(R("velocity_x") ** 2 + R("velocity_y") ** 2 + R("velocity_z") ** 2)
    accel = np.sqrt(R("accel_x") ** 2 + R("accel_y") ** 2 + R("accel_z") ** 2)

    signals = {
        "speed": speed, "accel": accel, "roll": R("roll"), "pitch": R("pitch"),
        "yaw_rate": R("yaw_rate"), "altitude": R("position_z"),
        "gnss_sat": R("gnss_sat_count"), "hdop": R("hdop"), "vdop": R("vdop"),
        "gnss_residual": R("gnss_residual"), "disagreement": disagreement,
        "battery": R("battery"), "rssi": R("rssi"), "sinr": R("sinr"),
        "pps": R("packets_per_second"), "bps": R("bytes_per_second"),
        "flow_dur": R("mean_flow_duration"), "active_flows": R("active_flows"),
        "dest_fanout": R("destination_fanout"), "src_fanout": R("source_fanout"),
        "packet_loss": R("packet_loss"), "retransmission": R("retransmission_rate"),
        "rtt": R("rtt"), "jitter": R("jitter"), "route_changes": R("route_changes"),
        "routing_ctrl": R("routing_control_rate"), "neighbour_churn": R("neighbour_churn"),
        "failed_conn": R("failed_connections"), "command_rate": R("command_rate"),
        "unauth_cmd": R("unauthorised_command_count"),
        "session_est": R("session_establishment_rate"),
        "session_term": R("session_termination_rate"),
        "auth_fail": R("authentication_failures"), "cred_changes": R("credential_changes"),
        "gcs_fanout": R("gcs_fanout"), "unexpected_operator": R("unexpected_operator"),
        "unusual_seq": R("unusual_command_sequence_score"),
        "session_origin_change": R("session_origin_change"),
        "priv_escalation": R("privilege_escalation_count"),
    }

    n_windows = max((n_steps - win) // stride + 1, 1)
    starts = np.arange(n_windows) * stride

    # Cache sliding views per needed signal + reduction.
    feats: dict[str, np.ndarray] = {}
    needed: dict[str, list[str]] = {}
    for _out, sig, op in _AGG_SPEC:
        needed.setdefault(sig, []).append(op)
    view_cache: dict[str, np.ndarray] = {sig: _windows(signals[sig], win, starts) for sig in needed}
    for out, sig, op in _AGG_SPEC:
        feats[out] = _REDUCE[op](view_cache[sig])

    feats["net_protocol_entropy"] = _entropy_feature(R("protocol_code"), win, starts, 3)
    feats["beh_command_type_entropy"] = _entropy_feature(R("command_type_code"), win, starts, 4)

    # Labels / metadata per (uav, window).
    is_attack = R("is_attack").astype(bool)
    labels = R("attack_label")
    origin = R("attack_origin")
    onset = R("attack_onset")
    intensity = R("attack_intensity")
    impact = R("mission_impact").astype(bool)
    phase = frame["mission_phase"].to_numpy().reshape(n, n_steps)
    timeline = frame["timestamp"].to_numpy().reshape(n, n_steps)[0]

    frac = _windows(is_attack.astype(float), win, starts).mean(axis=2)  # (n, n_windows)
    impact_win = _windows(impact.astype(float), win, starts).max(axis=2) > 0

    # Per-UAV attack identity (single attack per mission).
    uav_label = np.full(n, "benign", dtype=object)
    uav_origin = np.full(n, "", dtype=object)
    uav_onset = np.full(n, np.nan)
    uav_intensity = np.zeros(n)
    for u in range(n):
        atk = is_attack[u]
        if atk.any():
            vals = labels[u][atk]
            uav_label[u] = vals[0]
            uav_origin[u] = origin[u][atk][0]
            uav_onset[u] = float(np.nanmin(onset[u][atk]))
            uav_intensity[u] = float(np.nanmax(intensity[u][atk]))

    # Dominant phase per window (mode) via a small vectorised pass.
    phase_win = _mode_phase(phase, win, starts)

    rows: dict[str, np.ndarray] = {}
    uav_idx = np.repeat(np.arange(n), n_windows)
    win_ids = np.tile(np.arange(n_windows), n)
    is_atk_flat = (frac >= 0.5).reshape(-1)
    rows["scenario_id"] = np.full(n * n_windows, mission.scenario_id, dtype=object)
    rows["run_id"] = np.full(n * n_windows, mission.run_id, dtype=object)
    rows["seed"] = np.full(n * n_windows, mission.seed)
    rows["uav_id"] = np.array([f"uav_{u:02d}" for u in uav_idx], dtype=object)
    rows["uav_index"] = uav_idx
    rows["window_id"] = win_ids
    rows["window_start"] = timeline[starts][win_ids]
    rows["mission_phase"] = phase_win.reshape(-1)
    label_grid = np.where(frac >= 0.5, uav_label[:, None], "benign")
    rows["attack_label"] = label_grid.reshape(-1)
    rows["attack_origin"] = np.where(frac >= 0.5, uav_origin[:, None], "").reshape(-1)
    rows["attack_onset"] = np.where(frac >= 0.5, uav_onset[:, None], np.nan).reshape(-1)
    rows["attack_intensity"] = np.where(frac >= 0.5, uav_intensity[:, None], 0.0).reshape(-1)
    rows["mission_impact_window"] = impact_win.reshape(-1)
    rows["is_attack"] = is_atk_flat
    for name, grid in feats.items():
        rows[name] = grid.reshape(-1)

    df = pd.DataFrame(rows)
    df = _add_cross_vehicle(df)
    return df


def _mode_phase(phase: np.ndarray, win: int, starts: np.ndarray) -> np.ndarray:
    """Most-frequent phase label per window (phases are contiguous, so mid-point
    of the window is a fast, accurate proxy)."""
    n, _ = phase.shape
    mid = starts + win // 2
    return phase[:, mid]


def _add_cross_vehicle(df: pd.DataFrame) -> pd.DataFrame:
    for feat, source in _XV_SOURCE.items():
        grp = df.groupby("window_id")[source]
        mean = grp.transform("mean")
        std = grp.transform("std").replace(0, np.nan)
        df[feat] = ((df[source] - mean) / std).fillna(0.0)
    return df
