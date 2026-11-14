"""Physics-informed feature extraction for QKD telemetry classification.

Extracts 24 features from raw telemetry, organized by source group
(quantum statistics, terminal telemetry, receiver monitors, derived).
"""
import numpy as np
import pandas as pd
from .linkmodel import Link, slant_range

FEATURE_REGISTRY = [
    dict(name='loss_residual', unit='dB', equation='obs_loss - model_loss(elev)',
         group='q', quantum_only=True),
    dict(name='qber_residual', unit='',
         equation='obs_qber - model_qber(elev)', group='q', quantum_only=True),
    dict(name='vacuum_rate_residual', unit='',
         equation='obs_vac - model_vac(elev)', group='q', quantum_only=True),
    dict(name='decoy_ratio_deviation', unit='',
         equation='obs_decoy - 1.0', group='q', quantum_only=True),
    dict(name='basis_ratio_deviation', unit='',
         equation='obs_basis - p_x', group='q', quantum_only=True),
    dict(name='beacon_power_ratio', unit='',
         equation='beacon_down / beacon_up', group='t', quantum_only=False),
    dict(name='beacon_residual_down', unit='',
         equation='obs_down - model_down(elev)', group='t', quantum_only=False),
    dict(name='beacon_residual_up', unit='',
         equation='obs_up - model_up(elev)', group='t', quantum_only=False),
    dict(name='pointing_residual_norm', unit='sigma',
         equation='pointing / sigma_j', group='t', quantum_only=False),
    dict(name='scintillation_index', unit='',
         equation='measured scintillation', group='t', quantum_only=False),
    dict(name='out_of_gate_norm', unit='',
         equation='out_of_gate / baseline', group='r', quantum_only=False),
    dict(name='double_click_norm', unit='',
         equation='double_click / baseline', group='r', quantum_only=False),
    dict(name='pol_reference_deviation', unit='rad',
         equation='|pol_ref - 0|', group='r', quantum_only=False),
    dict(name='loss_rate_of_change', unit='dB/s',
         equation='d(loss)/dt', group='q', quantum_only=True),
    dict(name='qber_rate_of_change', unit='1/s',
         equation='d(qber)/dt', group='q', quantum_only=True),
    dict(name='beacon_rate_of_change', unit='1/s',
         equation='d(beacon_down)/dt', group='t', quantum_only=False),
    dict(name='rolling_mean_loss', unit='dB',
         equation='mean(loss, 10s)', group='q', quantum_only=True),
    dict(name='rolling_std_loss', unit='dB',
         equation='std(loss, 10s)', group='q', quantum_only=True),
    dict(name='rolling_mean_qber', unit='',
         equation='mean(qber, 10s)', group='q', quantum_only=True),
    dict(name='rolling_std_qber', unit='',
         equation='std(qber, 10s)', group='q', quantum_only=True),
    dict(name='elevation_norm', unit='',
         equation='elev_deg / 90', group='l', quantum_only=False),
    dict(name='atm_transmittance_dev', unit='',
         equation='obs_atm - model_atm(elev)', group='l', quantum_only=False),
    dict(name='signal_to_noise', unit='dB',
         equation='10 log10(signal / y0)', group='q', quantum_only=True),
    dict(name='anomaly_distance', unit='',
         equation='Mahalanobis from nominal centroid', group='derived',
         quantum_only=False),
]

FEATURE_NAMES = [f['name'] for f in FEATURE_REGISTRY]
QUANTUM_ONLY = [f['name'] for f in FEATURE_REGISTRY if f['quantum_only']]


def feature_dictionary():
    """Return the feature dictionary as a DataFrame."""
    return pd.DataFrame(FEATURE_REGISTRY)


def _model_values(link, elev_deg):
    """Compute model-predicted observables at each elevation."""
    elev_rad = np.radians(elev_deg)
    L = slant_range(elev_rad, 500e3)
    eta = link.eta(L, elev_rad)
    rate, qber = link.rate(eta)
    loss = link.loss_db(L, elev_rad)
    y0 = link.y0()
    q_mu = y0 + 1.0 - np.exp(-eta * link.mu)
    vac = np.where(q_mu > 1e-15, y0 / q_mu, 0.5)
    atm = link.eta_atm(elev_rad)
    beacon_model = 0.8 * atm
    return dict(model_loss=loss, model_qber=qber, model_vac=vac,
                model_atm=atm, model_beacon=beacon_model, y0=y0,
                signal_count_model=rate / link.f_rep)


def extract_features(df, link=None):
    """Extract the 24 physics-informed features from a telemetry DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Output of ``generate_pass`` or ``generate_dataset``.
    link : Link or None
        Link parameters for model residuals. Uses default if None.

    Returns
    -------
    np.ndarray
        Feature matrix of shape (n_windows, 24).
    """
    if link is None:
        link = Link()

    mv = _model_values(link, df['elevation_deg'].values)

    feats = np.empty((len(df), 24), dtype=np.float64)

    feats[:, 0] = df['loss_db'].values - mv['model_loss']
    feats[:, 1] = df['qber'].values - mv['model_qber']
    feats[:, 2] = df['vacuum_rate'].values - mv['model_vac']
    feats[:, 3] = df['decoy_ratio'].values - 1.0
    feats[:, 4] = df['basis_ratio'].values - link.p_x

    bd = df['beacon_down'].values
    bu = df['beacon_up'].values
    feats[:, 5] = np.where(bu > 1e-10, bd / bu, 1.0)
    feats[:, 6] = bd - mv['model_beacon']
    feats[:, 7] = bu - 0.75 * mv['model_atm']

    feats[:, 8] = df['pointing_residual'].values / link.sigma_j
    feats[:, 9] = df['scintillation_index'].values

    feats[:, 10] = df['out_of_gate_rate'].values / 0.001
    feats[:, 11] = df['double_click_rate'].values / 0.0005
    feats[:, 12] = np.abs(df['pol_reference'].values)

    loss = df['loss_db'].values
    qber = df['qber'].values
    feats[:, 13] = np.gradient(loss)
    feats[:, 14] = np.gradient(qber)
    feats[:, 15] = np.gradient(bd)

    # rolling stats with per-pass boundaries
    win = 10
    r_mean_loss = pd.Series(loss).rolling(win, min_periods=1, center=True).mean().values
    r_std_loss = pd.Series(loss).rolling(win, min_periods=1, center=True).std().fillna(0).values
    r_mean_qber = pd.Series(qber).rolling(win, min_periods=1, center=True).mean().values
    r_std_qber = pd.Series(qber).rolling(win, min_periods=1, center=True).std().fillna(0).values

    feats[:, 16] = r_mean_loss
    feats[:, 17] = r_std_loss
    feats[:, 18] = r_mean_qber
    feats[:, 19] = r_std_qber

    feats[:, 20] = df['elevation_deg'].values / 90.0
    feats[:, 21] = df['atm_transmittance'].values - mv['model_atm']

    sc = df['signal_count'].values
    feats[:, 22] = np.where(sc > 1e-15, 10 * np.log10(sc / mv['y0']), 0)

    # anomaly distance: L2 from per-column mean of rows labelled nominal
    nom_mask = df['label'].values == 'nominal' if 'label' in df.columns else np.ones(len(df), bool)
    if nom_mask.any():
        mu = feats[nom_mask, :23].mean(axis=0)
        sigma = feats[nom_mask, :23].std(axis=0)
        sigma = np.where(sigma < 1e-12, 1.0, sigma)
        feats[:, 23] = np.sqrt(((feats[:, :23] - mu) / sigma) ** 2).mean(axis=1)
    else:
        feats[:, 23] = 0.0

    np.nan_to_num(feats, copy=False)
    return feats
