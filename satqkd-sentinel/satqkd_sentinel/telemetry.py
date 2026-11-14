"""Telemetry simulator for satellite QKD link states.

Generates synthetic 1-second telemetry windows for 10 link states:
nominal operation, five fault types, and four attack signatures,
following the signature matrix of Table 3 of the article.
"""
import numpy as np
import pandas as pd
from .linkmodel import Link, slant_range, pass_profile

STATES = [
    'nominal',
    'cloud_attenuation', 'pointing_degradation', 'opa_phase_drift',
    'natural_background', 'polarization_drift',
    'optical_jamming', 'intercept_resend', 'yield_manipulation',
    'detector_control',
]

GROUPS = {
    'nominal': 'nominal',
    'cloud_attenuation': 'fault', 'pointing_degradation': 'fault',
    'opa_phase_drift': 'fault', 'natural_background': 'fault',
    'polarization_drift': 'fault',
    'optical_jamming': 'attack', 'intercept_resend': 'attack',
    'yield_manipulation': 'attack', 'detector_control': 'attack',
}

_ELEVATION_MAXES = [25, 30, 40, 60, 90]


def _nominal_observables(link, elev_rad, L, rng):
    """Baseline observables for one window at given elevation."""
    eta = link.eta(L, elev_rad)
    rate_bps, qber = link.rate(eta)
    loss_db = link.loss_db(L, elev_rad)
    y0 = link.y0()
    q_mu = y0 + 1.0 - np.exp(-eta * link.mu)

    signal_count = rate_bps / link.f_rep
    vacuum_rate = y0 / q_mu if q_mu > 1e-15 else 0.5
    decoy_ratio = 1.0
    basis_ratio = link.p_x

    beacon_down = 0.8 * link.eta_atm(elev_rad) * (1.0 + 0.02 * rng.standard_normal())
    beacon_up = 0.75 * link.eta_atm(elev_rad) * (1.0 + 0.02 * rng.standard_normal())
    pointing_res = link.sigma_j * rng.rayleigh(1.0)
    scintillation = 0.02 * (1.0 / np.sin(max(elev_rad, 0.05))) * (1.0 + 0.3 * rng.standard_normal())

    out_of_gate = 0.001 * (1.0 + 0.1 * rng.standard_normal())
    double_click = 0.0005 * (1.0 + 0.1 * rng.standard_normal())
    pol_ref = 0.0 + 0.005 * rng.standard_normal()

    return dict(
        signal_count=max(signal_count, 0),
        qber=np.clip(qber + 0.002 * rng.standard_normal(), 0, 0.5),
        vacuum_rate=np.clip(vacuum_rate + 0.005 * rng.standard_normal(), 0, 1),
        decoy_ratio=np.clip(decoy_ratio + 0.01 * rng.standard_normal(), 0.5, 1.5),
        basis_ratio=np.clip(basis_ratio + 0.005 * rng.standard_normal(), 0, 1),
        loss_db=loss_db,
        beacon_down=max(beacon_down, 0),
        beacon_up=max(beacon_up, 0),
        pointing_residual=max(pointing_res, 0),
        scintillation_index=max(scintillation, 0),
        out_of_gate_rate=max(out_of_gate, 0),
        double_click_rate=max(double_click, 0),
        pol_reference=pol_ref,
        rate_bps=rate_bps,
        eta=eta,
    )


def _apply_anomaly(obs, state, severity, rng):
    """Modify nominal observables according to the anomaly signature."""
    s = severity
    if state == 'cloud_attenuation':
        extra_loss = s * 8.0
        atten = 10 ** (-extra_loss / 10)
        obs['loss_db'] += extra_loss
        obs['signal_count'] *= atten
        obs['qber'] = np.clip(obs['qber'] + s * 0.05, 0, 0.5)
        obs['beacon_down'] *= max(1.0 - s * 0.6, 0.05)
        obs['beacon_up'] *= max(1.0 - s * 0.5, 0.05)

    elif state == 'pointing_degradation':
        extra_loss = s * 6.0
        atten = 10 ** (-extra_loss / 10)
        obs['loss_db'] += extra_loss
        obs['signal_count'] *= atten
        obs['pointing_residual'] += s * 15e-6
        obs['scintillation_index'] += s * 0.08

    elif state == 'opa_phase_drift':
        extra_loss = s * 5.0
        atten = 10 ** (-extra_loss / 10)
        obs['loss_db'] += extra_loss
        obs['signal_count'] *= atten

    elif state == 'natural_background':
        obs['vacuum_rate'] += s * 0.15
        obs['out_of_gate_rate'] += s * 0.01

    elif state == 'polarization_drift':
        obs['qber'] = np.clip(obs['qber'] + s * 0.08, 0, 0.5)
        obs['pol_reference'] += s * 0.15 * (1 if rng.random() > 0.5 else -1)

    elif state == 'optical_jamming':
        obs['qber'] = np.clip(obs['qber'] + s * 0.12, 0, 0.5)
        obs['vacuum_rate'] += s * 0.2
        obs['out_of_gate_rate'] += s * 0.02
        obs['double_click_rate'] += s * 0.005

    elif state == 'intercept_resend':
        obs['qber'] = np.clip(obs['qber'] + s * 0.10, 0, 0.5)

    elif state == 'yield_manipulation':
        obs['decoy_ratio'] -= s * 0.25

    elif state == 'detector_control':
        obs['qber'] = np.clip(obs['qber'] - s * 0.03, 0, 0.5)
        obs['vacuum_rate'] = max(obs['vacuum_rate'] - s * 0.1, 0)
        obs['basis_ratio'] += s * 0.08 * (1 if rng.random() > 0.5 else -1)
        obs['out_of_gate_rate'] = max(obs['out_of_gate_rate'] - s * 0.0008, 0)
        obs['double_click_rate'] = max(obs['double_click_rate'] - s * 0.0003, 0)

    return obs


def generate_pass(link, eps_max_rad, state='nominal', severity=0.5,
                  onset_fraction=0.3, seed=None):
    """Generate telemetry for one satellite pass.

    Parameters
    ----------
    link : Link
        Baseline link parameters.
    eps_max_rad : float
        Maximum elevation of the pass in radians.
    state : str
        One of STATES.
    severity : float
        Anomaly severity in [0, 1].
    onset_fraction : float
        Fraction of the pass before the anomaly begins (0 = from start).
    seed : int or None
        Random seed.

    Returns
    -------
    pd.DataFrame
        One row per 1-second window with raw observables and metadata.
    """
    rng = np.random.default_rng(seed)
    t, elev, L, az = pass_profile(eps_max_rad)
    n = len(t)
    onset_idx = int(onset_fraction * n) if state != 'nominal' else n

    rows = []
    for i in range(n):
        obs = _nominal_observables(link, elev[i], L[i], rng)
        active = state if i >= onset_idx else 'nominal'
        if active != 'nominal':
            obs = _apply_anomaly(obs, state, severity, rng)
        rows.append(dict(
            t_s=t[i] - t[0],
            elevation_deg=np.degrees(elev[i]),
            slant_range_km=L[i] / 1e3,
            atm_transmittance=float(link.eta_atm(elev[i])),
            label=active,
            group=GROUPS[active],
            severity=severity if active != 'nominal' else 0.0,
            onset_s=(t[onset_idx] - t[0]) if state != 'nominal' else float('nan'),
            **{k: v for k, v in obs.items()},
        ))
    return pd.DataFrame(rows)


def generate_dataset(link, n_passes, class_distribution=None, seed=42):
    """Generate a multi-pass dataset with mixed link states.

    Parameters
    ----------
    link : Link
        Baseline link parameters.
    n_passes : int
        Total number of passes.
    class_distribution : dict or None
        Maps state name to fraction of passes. Defaults to
        40 % nominal, 6 % each fault, 7.5 % each attack.
    seed : int
        Master random seed.

    Returns
    -------
    pd.DataFrame
        Concatenated telemetry with a ``pass_id`` column.
    """
    if class_distribution is None:
        class_distribution = {'nominal': 0.40}
        for f in STATES[1:6]:
            class_distribution[f] = 0.06
        for a in STATES[6:]:
            class_distribution[a] = 0.075

    rng = np.random.default_rng(seed)
    frames = []
    pass_id = 0

    for state, frac in class_distribution.items():
        count = max(1, round(frac * n_passes))
        for _ in range(count):
            eps_max = np.radians(rng.choice(_ELEVATION_MAXES))
            sev = rng.uniform(0.3, 1.0) if state != 'nominal' else 0.0
            onset = rng.uniform(0.1, 0.5) if state != 'nominal' else 0.0
            df = generate_pass(link, eps_max, state=state, severity=sev,
                               onset_fraction=onset, seed=rng.integers(0, 2**31))
            df['pass_id'] = pass_id
            frames.append(df)
            pass_id += 1

    return pd.concat(frames, ignore_index=True)
