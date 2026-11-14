"""Trusted-relay network model (Equations (17)-(22) of the article).

Key store dynamics, network availability, relay consumption and cost.
"""
import numpy as np
from .linkmodel import Link, pass_profile


def key_per_pass(link, eps_max_rad):
    """Asymptotic key generated in one satellite pass (bits)."""
    eps_max_rad = float(eps_max_rad)
    t, el, L, az = pass_profile(eps_max_rad)
    r, _ = link.rate(link.eta(L, el))
    dt = t[1] - t[0] if len(t) > 1 else 1.0
    return float(r.sum() * dt)


def key_per_day(link, passes_per_day, eps_max_rad=None):
    """Total asymptotic key per day (bits) for repeated passes.

    Parameters
    ----------
    link : Link
    passes_per_day : int
    eps_max_rad : float or list of float
        Maximum elevation per pass (scalar = same for all passes).
    """
    if eps_max_rad is None:
        eps_max_rad = np.radians(40)

    if np.isscalar(eps_max_rad):
        return key_per_pass(link, eps_max_rad) * passes_per_day

    total = 0.0
    for em in eps_max_rad[:passes_per_day]:
        total += key_per_pass(link, float(em))
    return total


def relay_key_consumption(n_hops, message_bits, otp=True):
    """Key consumed for a single message traversing n_hops trusted relays.

    With OTP each hop consumes message_bits of key.
    With AES-256 each hop consumes 256 bits.
    """
    per_hop = message_bits if otp else 256
    return n_hops * per_hop


def key_store_model(generation_rate_bps, consumption_rate_bps, store_capacity_bits,
                    days=30, dt_hours=1.0, pass_duration_s=360, passes_per_day=3, seed=42):
    """Simulate key-store dynamics over time.

    Returns dict with time (hours), store level, overflow and underflow events.
    """
    rng = np.random.default_rng(seed)
    n_steps = int(days * 24 / dt_hours)
    t = np.arange(n_steps) * dt_hours
    store = np.zeros(n_steps)
    store[0] = store_capacity_bits * 0.5
    overflow = 0
    underflow = 0
    pass_prob_per_step = passes_per_day / (24.0 / dt_hours)

    for i in range(1, n_steps):
        generated = 0.0
        if rng.random() < pass_prob_per_step:
            generated = generation_rate_bps * pass_duration_s
        consumed = consumption_rate_bps * dt_hours * 3600
        new_level = store[i - 1] + generated - consumed
        if new_level > store_capacity_bits:
            overflow += new_level - store_capacity_bits
            new_level = store_capacity_bits
        if new_level < 0:
            underflow += abs(new_level)
            new_level = 0
        store[i] = new_level

    return dict(t_hours=t, store=store, overflow_bits=overflow,
                underflow_bits=underflow, days=days)


def network_availability(n_nodes, link_availability, redundancy=1):
    """Probability that at least `redundancy` paths exist in a ring of n_nodes."""
    from math import comb
    p = link_availability
    if redundancy == 1:
        return 1.0 - (1.0 - p) ** n_nodes
    return 1.0 - sum(
        comb(n_nodes, k) * p**k * (1 - p)**(n_nodes - k)
        for k in range(redundancy)
    )


def cost_model(n_ground, n_relay, n_geo):
    """Relative cost index (arbitrary units).

    Ground station ~ 1, LEO relay ~ 5, GEO node ~ 20.
    """
    return n_ground * 1.0 + n_relay * 5.0 + n_geo * 20.0


def daily_key_budget(link=None, passes_per_day_list=None, eps_max_rad=None):
    """Total daily key for varying numbers of passes.

    Returns a dict mapping passes_per_day to daily key in bits.
    """
    if link is None:
        link = Link()
    if eps_max_rad is None:
        eps_max_rad = np.radians(40)
    if passes_per_day_list is None:
        passes_per_day_list = [1, 2, 4, 8]

    k_pass = key_per_pass(link, float(eps_max_rad))
    return {p: k_pass * p for p in passes_per_day_list}
