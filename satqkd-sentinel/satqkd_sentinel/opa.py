"""Optical Phased Array (OPA) model (Equations (12)-(16) of the article).

Uniform rectangular array: N_el elements per axis, element spacing d,
operating wavelength 1550 nm. Beam steering, sidelobe analysis, and
Monte Carlo phase-error loss estimation.
"""
import numpy as np


def array_factor_1d(theta, theta_s, n_el=4096, d=2e-6, wavelength=1550e-9):
    """Normalised 1-D array factor |AF|^2 / N^2 for a uniform linear array.

    theta, theta_s : observation and steering angles (rad)
    """
    theta = np.asarray(theta, dtype=float)
    k = 2.0 * np.pi / wavelength
    psi = k * d * (np.sin(theta) - np.sin(theta_s))
    with np.errstate(invalid='ignore', divide='ignore'):
        af = np.where(
            np.abs(psi) < 1e-12,
            1.0,
            (np.sin(n_el * psi / 2.0) / (n_el * np.sin(psi / 2.0)))**2
        )
    return af


def beam_pattern(theta, theta_s, n_el=4096, d=2e-6, wavelength=1550e-9, sigma_phi=0.0):
    """1-D beam pattern with optional random phase errors.

    When sigma_phi > 0, a single realisation of i.i.d. Gaussian phase
    errors is applied to the element phases.
    """
    theta = np.asarray(theta, dtype=float)
    if sigma_phi <= 0:
        return array_factor_1d(theta, theta_s, n_el, d, wavelength)

    k = 2.0 * np.pi / wavelength
    rng = np.random.default_rng(42)
    phase_err = rng.normal(0, sigma_phi, n_el)

    elements = np.arange(n_el)
    steer_phase = k * d * elements * np.sin(theta_s)

    af = np.zeros(len(theta), dtype=complex)
    for i, th in enumerate(theta):
        obs_phase = k * d * elements * np.sin(th)
        af[i] = np.sum(np.exp(1j * (obs_phase - steer_phase + phase_err)))

    return np.abs(af)**2 / n_el**2


def steering_range(d=2e-6, wavelength=1550e-9):
    """Maximum steering half-angle (rad) to avoid grating lobes."""
    ratio = wavelength / (2.0 * d)
    return np.arcsin(min(ratio, 1.0))


def beam_width(n_el=4096, d=2e-6, wavelength=1550e-9):
    """First-null beam width approximation (rad), close to FWHM for large arrays."""
    return wavelength / (n_el * d)


def phase_error_loss_db(sigma_phi, n_samples=10000, seed=42):
    """Monte Carlo estimate of the on-axis power loss due to i.i.d.
    Gaussian phase errors across the array elements (1-D, single axis).

    Returns loss in dB (positive means the beam is weaker).
    """
    rng = np.random.default_rng(seed)
    phases = rng.normal(0, sigma_phi, (n_samples,))
    mean_phasor = np.abs(np.mean(np.exp(1j * phases)))
    strehl = mean_phasor**2
    if strehl < 1e-30:
        return 100.0
    return -10.0 * np.log10(strehl)


def sidelobe_level_db(n_el=4096, d=2e-6, wavelength=1550e-9):
    """First sidelobe level relative to the main lobe (dB, negative).

    For a uniform linear array the first sidelobe is at -13.26 dB
    for large N, independent of d and wavelength.
    """
    theta_null = np.arcsin(wavelength / (n_el * d))
    theta_sl = np.arcsin(1.5 * wavelength / (n_el * d))
    main = 1.0
    sl = array_factor_1d(theta_sl, 0.0, n_el, d, wavelength)
    if sl <= 0:
        return -100.0
    return 10.0 * np.log10(float(sl) / main)


def element_pitch_um(wavelength=1550e-9):
    """Half-wavelength pitch in micrometres (Nyquist spacing)."""
    return wavelength / 2.0 * 1e6


def far_field_divergence(n_el=4096, d=2e-6, wavelength=1550e-9):
    """Far-field half-angle divergence (rad) of the main lobe."""
    return 0.886 * wavelength / (n_el * d)
