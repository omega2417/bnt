"""Illustrative decoy-state finite-size estimate for BB84-QKD.

Three-intensity protocol: signal (mu), weak decoy (nu1), vacuum decoy (nu2 ~ 0).
The yield approximation is inspired by Ma et al. (PRA 72, 012326, 2005).
Fluctuation and phase-error penalties are simplified; this is NOT an
implementation of a composable security proof or deployable key generation.
"""
import numpy as np
from .linkmodel import Link, pass_profile, h2


def _delta(n, eps):
    """Multiplicative fluctuation on a gain observed with n detection events."""
    if n <= 0:
        return 1.0
    return np.sqrt(-np.log(eps) / (2.0 * n))


def finite_key_length(n_mu, n_nu1, n_nu2, E_mu,
                       N_mu_sent, N_nu1_sent, N_nu2_sent,
                       f_ec=1.16, eps=1e-10,
                       mu=0.5, nu1=0.1, nu2=0.001, p_x=0.8):
    """Illustrative finite-size key estimate in bits, not a security certificate.

    Expected counts may be fractional. All observed signal errors contribute to
    the phase-error estimate; the signal/decoy allocation is 50/25/25 percent in
    ``finite_key_pass``. The near-vacuum gain is used as a conservative background
    proxy; statistical fluctuations remain an approximation.
    """
    values = [n_mu,n_nu1,n_nu2,E_mu,N_mu_sent,N_nu1_sent,N_nu2_sent,f_ec,eps,mu,nu1,nu2,p_x]
    if not np.isfinite(values).all():
        raise ValueError("Finite-key inputs must be finite")
    if not 0 < eps < 1 or not 0 <= E_mu <= .5 or not 0 < p_x < 1 or f_ec < 1:
        raise ValueError("Require 0 < eps,p_x < 1, 0 <= E_mu <= .5 and f_ec >= 1")
    if not 0 <= nu2 < nu1 < mu or nu1 + nu2 >= mu:
        raise ValueError("Require 0 <= nu2 < nu1 and nu1 + nu2 < mu")
    if min(n_mu,n_nu1,n_nu2,N_mu_sent,N_nu1_sent,N_nu2_sent) < 0:
        raise ValueError("Counts must be nonnegative")
    if any(n > N for n,N in zip((n_mu,n_nu1,n_nu2),(N_mu_sent,N_nu1_sent,N_nu2_sent))):
        raise ValueError("Detections cannot exceed sent pulses")
    if min(N_mu_sent,N_nu1_sent,N_nu2_sent) == 0:
        return 0.0
    if n_mu <= 0 or n_nu1 <= 0 or N_mu_sent <= 0:
        return 0.0

    eps_s = eps / 5.0

    Q_mu = n_mu / N_mu_sent
    Q_nu1 = n_nu1 / N_nu1_sent
    Q_nu2 = n_nu2 / max(N_nu2_sent, 1)

    dQ_mu = Q_mu * _delta(n_mu, eps_s)
    dQ_nu1 = Q_nu1 * _delta(n_nu1, eps_s)
    dQ_nu2 = max(Q_nu2, 1e-20) * _delta(max(n_nu2, 1), eps_s)

    Y0_upper = Q_nu2 + dQ_nu2

    # Ma-Qi-Lo lower bound on single-photon yield
    prefactor = mu * np.exp(nu1) / (mu * nu1 - nu1**2)
    Y1_lower = prefactor * (
        (Q_nu1 - dQ_nu1)
        - nu1**2 / mu**2 * (Q_mu + dQ_mu) * np.exp(mu - nu1)
        - (mu**2 - nu1**2) / mu**2 * Y0_upper
    )
    Y1_lower = np.clip(Y1_lower, 0, 1)

    if Y1_lower <= 0:
        return 0.0

    # Lower bound on single-photon X-basis detections
    n1_x = N_mu_sent * p_x**2 * mu * np.exp(-mu) * Y1_lower
    n1_x_lower = n1_x - np.sqrt(n1_x * np.log(1.0 / eps_s) / 2.0)
    n1_x_lower = max(n1_x_lower, 0)

    if n1_x_lower <= 0:
        return 0.0

    # Upper bound on single-photon phase-error rate
    # Attribute all observed signal errors to single-photon events. The old
    # expression counted only background and ignored optical/misalignment errors.
    error_count = n_mu * E_mu
    error_gain_upper = (error_count + np.sqrt(max(error_count, 1) * np.log(1/eps_s) / 2)) / N_mu_sent
    e1_upper = error_gain_upper * np.exp(mu) / max(mu * Y1_lower, 1e-30)
    e1_upper = np.clip(e1_upper, 0, 0.5)

    # Finite-size phase-error correction
    phi = e1_upper + np.sqrt(np.log(21.0 / eps_s) / (2.0 * n1_x_lower))
    phi = min(phi, 0.5)

    # Error correction
    E_clip = np.clip(E_mu, 1e-15, 0.5 - 1e-15)
    n_mu_x = n_mu * p_x**2
    leak_ec = f_ec * n_mu_x * h2(E_clip)

    # Privacy amplification
    log_corr = 6.0 * np.log2(19.0 / eps) + np.log2(2.0 / eps)

    key = n1_x_lower * (1.0 - h2(np.clip(phi, 1e-15, 0.5 - 1e-15))) - leak_ec - log_corr
    return max(key, 0.0)


def _counts_for_samples(link, eta, dt, mu, nu1, nu2):
    result = {}
    for name, intensity, fraction in [('mu',mu,.5),('nu1',nu1,.25),('nu2',nu2,.25)]:
        sent_per_window = link.f_rep * dt * fraction
        signal = -np.expm1(-eta * intensity)
        gains = link.y0() + signal
        detected = float(sent_per_window * gains.sum())
        errors = float(sent_per_window * (0.5*link.y0() + link.e_d*signal).sum())
        result[name] = dict(n_sent=sent_per_window * len(eta), n_det=detected,
                            e_avg=errors/max(detected, 1e-30))
    return result


def _pass_counts(link, eps_max_rad, mu=0.5, nu1=0.1, nu2=0.001):
    """Accumulate expected detection counts over all one-second pass windows."""
    t, el, L, _ = pass_profile(eps_max_rad)
    return _counts_for_samples(link, link.eta(L,el), 1.0, mu, nu1, nu2)


def finite_key_pass(link, eps_max_rad, block_size_s=None, eps=1e-10):
    """Sum finite-size estimates over blocks; default is a single pass block.

    Blocks are integer one-second windows. The epsilon budget is divided among
    blocks. This simplified estimate is not a composable security bound.
    """
    if not np.isfinite(eps) or not 0 < eps < 1:
        raise ValueError("eps must be in (0, 1)")
    if block_size_s is not None and (not np.isfinite(block_size_s) or block_size_s < 1 or int(block_size_s) != block_size_s):
        raise ValueError("block_size_s must be a positive integer number of seconds")
    t, el, L, _ = pass_profile(eps_max_rad)
    eta = link.eta(L, el)
    size = len(t) if block_size_s is None else int(block_size_s)
    n_blocks = int(np.ceil(len(t)/size))
    total = 0.0
    for start in range(0, len(t), size):
        c = _counts_for_samples(link, eta[start:start+size], 1., link.mu, .1, .001)
        total += finite_key_length(
            c['mu']['n_det'],c['nu1']['n_det'],c['nu2']['n_det'],c['mu']['e_avg'],
            c['mu']['n_sent'],c['nu1']['n_sent'],c['nu2']['n_sent'],
            link.f_ec, eps/n_blocks, link.mu,.1,.001,link.p_x)
    return float(total)


def finite_key_ratio(link, eps_max_rad, eps=1e-10):
    """Ratio of finite key to asymptotic key for a pass."""
    t, el, L, az = pass_profile(eps_max_rad)
    r_asym = link.rate(link.eta(L, el))[0].sum()
    k_finite = finite_key_pass(link, eps_max_rad, eps=eps)
    return k_finite / max(r_asym, 1e-30)


def asymptotic_vs_finite(link=None, eps_max_list=None, eps=1e-10):
    """Compare asymptotic and finite-key lengths for a set of pass elevations.

    Returns a list of dicts with eps_max_deg, K_inf (bits), K_fin (bits), ratio.
    """
    if link is None:
        link = Link()
    if eps_max_list is None:
        eps_max_list = [25, 30, 40, 60, 90]

    results = []
    for deg in eps_max_list:
        rad = np.radians(deg)
        t, el, L, az = pass_profile(rad)
        dt = t[1] - t[0] if len(t) > 1 else 1.0
        r_asym, _ = link.rate(link.eta(L, el))
        k_inf = float(r_asym.sum() * dt)
        k_fin = float(finite_key_pass(link, rad, eps=eps))
        ratio = k_fin / k_inf if k_inf > 0 else 0.0
        results.append(dict(eps_max_deg=deg, K_inf_bits=k_inf, K_fin_bits=k_fin, ratio=ratio))
    return results
