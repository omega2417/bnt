"""Decoy-state finite-key analysis for BB84-QKD (Equation (10) of the article).

Three-intensity protocol: signal (mu), weak decoy (nu1), vacuum decoy (nu2 ~ 0).
Yield bounds follow Ma, Qi, Lo (PRA 72, 012326, 2005). Finite-key
corrections from Lim, Curty, Walenta, Xu, Zbinden (PRA 89, 022307, 2014).
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
    """Finite-key secret-key length (bits)."""
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
    e1_upper = (Y0_upper / 2.0) / max(Y1_lower, 1e-30)
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


def _pass_counts(link, eps_max_rad, mu=0.5, nu1=0.1, nu2=0.001):
    """Accumulate expected detection counts over a full satellite pass."""
    t, el, L, az = pass_profile(eps_max_rad)
    dt = t[1] - t[0] if len(t) > 1 else 1.0

    y0 = link.y0()
    ed = link.e_d
    f_rep = link.f_rep

    result = {}
    for name, intensity, frac in [('mu', mu, 0.5), ('nu1', nu1, 0.25), ('nu2', nu2, 0.25)]:
        n_sent_total = 0.0
        n_det_total = 0.0
        e_weighted = 0.0

        for i in range(len(t)):
            eta_i = float(link.eta(L[i], el[i]))
            n_sent_i = f_rep * dt * frac
            q_i = y0 + 1.0 - np.exp(-eta_i * intensity)
            n_det_i = n_sent_i * q_i
            e_i = (0.5 * y0 + ed * (1.0 - np.exp(-eta_i * intensity))) / max(q_i, 1e-30)

            n_sent_total += n_sent_i
            n_det_total += n_det_i
            e_weighted += e_i * n_det_i

        result[name] = dict(n_sent=n_sent_total, n_det=n_det_total,
                            e_avg=e_weighted / max(n_det_total, 1e-30))

    return result


def finite_key_pass(link, eps_max_rad, block_size_s=None, eps=1e-10):
    """Finite-key length for an entire satellite pass (bits)."""
    mu, nu1_val, nu2_val = link.mu, 0.1, 0.001
    c = _pass_counts(link, eps_max_rad, mu, nu1_val, nu2_val)

    return finite_key_length(
        c['mu']['n_det'], c['nu1']['n_det'], c['nu2']['n_det'],
        c['mu']['e_avg'],
        c['mu']['n_sent'], c['nu1']['n_sent'], c['nu2']['n_sent'],
        link.f_ec, eps, mu, nu1_val, nu2_val, link.p_x
    )


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
