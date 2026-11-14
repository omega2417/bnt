"""Geostationary backbone: coverage, inter-satellite geometry, contact plan and link budgets.

Equations (28)-(33) of the revised article.
"""
import numpy as np
from .linkmodel import R_E, R_GEO, H_GEO, MU_E, Link, slant_range

OMEGA_E = 7.2921159e-5      # Earth rotation rate, rad/s
H_GRAZE = 100e3             # minimum height of an inter-satellite line of sight, m


def coverage_angle(eps_min_rad, r=R_GEO):
    """Eq. (28): geocentric half-angle of the zone seen above elevation eps_min."""
    return np.arccos(R_E * np.cos(eps_min_rad) / r) - eps_min_rad


def central_angle(lat, lon, lon_sat):
    """Geocentric angle between a ground point and the sub-satellite point (equator)."""
    return np.arccos(np.clip(np.cos(lat) * np.cos(lon - lon_sat), -1, 1))


def elevation(psi, r=R_GEO):
    """Eq. (29): elevation of a satellite at geocentric angle psi."""
    return np.arctan2(np.cos(psi) - R_E / r, np.sin(psi))


def range_from_angle(psi, r=R_GEO):
    return np.sqrt(R_E**2 + r**2 - 2 * R_E * r * np.cos(psi))


def isl_chord(n, r=R_GEO):
    """Eq. (30): distance between adjacent nodes of an n-node equatorial ring."""
    return 2 * r * np.sin(np.pi / n)


def isl_max_angle(r1, r2, h_graze=H_GRAZE):
    """Eq. (31): largest geocentric separation with a clear line of sight."""
    rg = R_E + h_graze
    return np.arccos(rg / r1) + np.arccos(rg / r2)


def slots(n, lon0_deg=35.0):
    return np.radians((lon0_deg + 360.0 * np.arange(n) / n + 180) % 360 - 180)


def coverage_stats(n, eps_min_deg=20.0, lon0_deg=35.0, nlat=721, nlon=1441):
    """Area-weighted shares of the Earth's surface that see >=1 and >=2 nodes."""
    lat = np.radians(np.linspace(-90, 90, nlat))
    lon = np.radians(np.linspace(-180, 180, nlon))
    LON, LAT = np.meshgrid(lon, lat)
    psi_max = coverage_angle(np.radians(eps_min_deg))
    k = np.zeros_like(LAT)
    best = np.full_like(LAT, -np.pi / 2)
    for ls in slots(n, lon0_deg):
        psi = central_angle(LAT, LON, ls)
        k += psi <= psi_max
        best = np.maximum(best, elevation(psi))
    w = np.cos(LAT)
    return dict(lat=lat, lon=lon, k=k, best_elev=best,
                share1=float((w * (k >= 1)).sum() / w.sum()),
                share2=float((w * (k >= 2)).sum() / w.sum()),
                lat_cont=_lat_continuous(n, psi_max))


def _lat_continuous(n, psi_max):
    """Highest latitude seen above eps_min at every longitude."""
    c = np.cos(psi_max) / np.cos(np.pi / n)
    return float(np.degrees(np.arccos(c))) if c <= 1 else float("nan")


# ---- contact plan of a LEO relay ---------------------------------------------------
def leo_eci(t, h=500e3, inc_deg=97.4, raan_deg=0.0, u0_deg=0.0):
    r = R_E + h
    n = np.sqrt(MU_E / r**3)
    u = np.radians(u0_deg) + n * t
    i, O = np.radians(inc_deg), np.radians(raan_deg)
    x = r * (np.cos(O) * np.cos(u) - np.sin(O) * np.sin(u) * np.cos(i))
    y = r * (np.sin(O) * np.cos(u) + np.cos(O) * np.sin(u) * np.cos(i))
    z = r * np.sin(u) * np.sin(i)
    return np.stack([x, y, z], -1)


def geo_eci(t, lon_rad):
    th = lon_rad + OMEGA_E * t
    return np.stack([R_GEO * np.cos(th), R_GEO * np.sin(th), np.zeros_like(th)], -1)


def site_eci(t, lat_deg, lon_deg):
    la, th = np.radians(lat_deg), np.radians(lon_deg) + OMEGA_E * t
    return np.stack([R_E * np.cos(la) * np.cos(th), R_E * np.cos(la) * np.sin(th),
                     R_E * np.sin(la) * np.ones_like(th)], -1)


def los_clear(p1, p2, h_graze=H_GRAZE):
    """True where the segment p1-p2 stays above R_E + h_graze."""
    d = p2 - p1
    s = np.clip(-(p1 * d).sum(-1) / (d * d).sum(-1), 0, 1)
    closest = p1 + s[..., None] * d
    return np.linalg.norm(closest, axis=-1) >= R_E + h_graze


def elev_from_site(site, sat):
    d = sat - site
    return np.arcsin((d * site).sum(-1) / (np.linalg.norm(d, axis=-1) * np.linalg.norm(site, axis=-1)))


def contact_plan(n_geo, sites, hours=24.0, dt=10.0, eps_min_deg=20.0, lon0_deg=35.0, **leo):
    """Visibility of a LEO relay from every GEO node and every ground site."""
    t = np.arange(0, hours * 3600 + dt / 2, dt)
    p = leo_eci(t, **leo)
    out = dict(t=t, geo=[], geo_range=[], site=[])
    for ls in slots(n_geo, lon0_deg):
        g = geo_eci(t, ls)
        out["geo"].append(los_clear(p, g))
        out["geo_range"].append(np.linalg.norm(g - p, axis=-1))
    for (la, lo) in sites:
        s = site_eci(t, la, lo)
        out["site"].append(elev_from_site(s, p) >= np.radians(eps_min_deg))
    out["geo"] = np.array(out["geo"]); out["geo_range"] = np.array(out["geo_range"])
    out["site"] = np.array(out["site"])
    return out


def max_gap_s(mask, dt):
    """Longest run of False in a boolean series, s."""
    best = run = 0
    for v in mask:
        run = 0 if v else run + 1
        best = max(best, run)
    return best * dt


# ---- OPA field of regard seen from GEO ------------------------------------------
def opa_footprint_km(d_out, n_el=4096, wavelength=1550e-9, rng=H_GEO):
    """Eq. (33): half field of regard (deg) and footprint radius at range rng (km)."""
    half = 0.5 * n_el * wavelength / d_out          # small-angle form of Eq. (15)
    return np.degrees(half), rng * np.tan(half) / 1e3
