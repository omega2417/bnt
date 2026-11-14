"""Link and key-rate model of the article (Equations (1)-(9)) - deterministic part.

Re-implementation used for the geostationary-backbone extension. All defaults are
the baseline parameters of Table 2 of the article.
"""
from dataclasses import dataclass, replace
import numpy as np

R_E = 6371.0e3          # Earth radius, m
MU_E = 3.986004418e14   # gravitational parameter, m^3/s^2
H_PLANCK = 6.62607015e-34
C_LIGHT = 2.99792458e8
H_GEO = 35786.0e3       # geostationary altitude, m
R_GEO = R_E + H_GEO


@dataclass(frozen=True)
class Link:
    wavelength: float = 1550e-9
    d_tx: float = 0.100            # output aperture, m
    d_rx: float = 0.600            # receiver aperture, m
    sigma_j: float = 2e-6          # pointing error per axis, rad
    eta_ml: float = 0.5            # main-lobe power fraction of the OPA
    t_zen: float = 0.9             # zenith transmittance
    eta_rx: float = 0.3 * 0.8      # receiver optics x detector
    f_rep: float = 500e6           # pulse rate, Hz
    e_d: float = 0.01              # optical error
    p_dc: float = 4e-7             # dark counts per gate (four detectors)
    h_b: float = 1e-4              # background radiance, W/(m^2 sr um)
    fov: float = 50e-6             # receiver field of view (full angle), rad
    dlam_um: float = 1e-3          # filter bandwidth, um
    gate: float = 1e-9             # gate, s
    mu: float = 0.5                # signal intensity
    p_x: float = 0.8               # X-basis probability
    f_ec: float = 1.16
    atmosphere: bool = True

    # ---- geometry and loss terms -------------------------------------------------
    @property
    def theta_w(self):
        return self.wavelength / (np.pi * self.d_tx / 3.0)          # Eq. (3)

    def eta_geo(self, L):
        a = self.d_rx / 2.0
        return 1.0 - np.exp(-2.0 * a**2 / (self.theta_w**2 * L**2))  # Eq. (3)

    def eta_pt(self):
        return 1.0 / (1.0 + 4.0 * self.sigma_j**2 / self.theta_w**2)  # Eq. (4)

    def eta_atm(self, elev_rad):
        if not self.atmosphere:
            return np.ones_like(np.asarray(elev_rad, dtype=float))
        return self.t_zen ** (1.0 / np.sin(elev_rad))                # Eq. (6)

    def eta(self, L, elev_rad=np.pi / 2):
        return (self.eta_geo(L) * self.eta_pt() * self.eta_atm(elev_rad)
                * self.eta_ml * self.eta_rx)                           # Eq. (2)

    def loss_db(self, L, elev_rad=np.pi / 2):
        return -10.0 * np.log10(self.eta(L, elev_rad))

    def components_db(self, L, elev_rad=np.pi / 2):
        f = lambda x: float(-10 * np.log10(x))
        return dict(diffraction=f(self.eta_geo(L)), pointing=f(self.eta_pt()),
                    atmosphere=f(self.eta_atm(elev_rad)), lobes=f(self.eta_ml),
                    receiver=f(self.eta_rx))

    # ---- detection and key rate --------------------------------------------------
    def y0(self):
        omega = np.pi * self.fov**2 / 4.0
        a_rx = np.pi * (self.d_rx / 2.0) ** 2
        e_ph = H_PLANCK * C_LIGHT / self.wavelength
        return self.p_dc + self.eta_rx * self.h_b * omega * a_rx * self.dlam_um * self.gate / e_ph  # Eq. (7)

    def rate(self, eta):
        """Asymptotic secret-key rate, bit/s (Eq. (9) times f_rep), and QBER."""
        eta = np.asarray(eta, dtype=float)
        y0, mu, ed = self.y0(), self.mu, self.e_d
        q_mu = y0 + 1.0 - np.exp(-eta * mu)                           # Eq. (8)
        e_mu = (0.5 * y0 + ed * (1.0 - np.exp(-eta * mu))) / q_mu
        q1 = (y0 + eta) * mu * np.exp(-mu)
        e1 = (0.5 * y0 + ed * eta) / (y0 + eta)
        r = self.p_x**2 * (q1 * (1.0 - h2(e1)) - self.f_ec * q_mu * h2(e_mu))
        return self.f_rep * np.maximum(r, 0.0), e_mu

    def loss_limit_db(self):
        """Largest channel loss at which the asymptotic rate is positive."""
        lo, hi = 20.0, 90.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.rate(10 ** (-mid / 10))[0] > 0:
                lo = mid
            else:
                hi = mid
        return lo

    def with_(self, **kw):
        return replace(self, **kw)


def h2(x):
    x = np.clip(np.asarray(x, dtype=float), 1e-15, 1 - 1e-15)
    return -x * np.log2(x) - (1 - x) * np.log2(1 - x)


def slant_range(elev_rad, h):
    """Eq. (1): slant range to a satellite at altitude h seen at elevation elev."""
    r = R_E + h
    return np.sqrt(r**2 - (R_E * np.cos(elev_rad)) ** 2) - R_E * np.sin(elev_rad)


def pass_profile(eps_max_rad, h=500e3, eps_min_rad=np.radians(20.0), dt=1.0):
    """Elevation, azimuth-like offset and range during a pass (non-rotating Earth)."""
    r = R_E + h
    w = np.sqrt(MU_E / r**3)
    gam = lambda e: np.arccos(R_E * np.cos(e) / r) - e
    g0, g1 = gam(eps_max_rad), gam(eps_min_rad)
    t_half = np.arccos(np.cos(g1) / np.cos(g0)) / w
    t = np.arange(-t_half, t_half + dt / 2, dt)
    g = np.arccos(np.cos(g0) * np.cos(w * t))
    L = np.sqrt(R_E**2 + r**2 - 2 * R_E * r * np.cos(g))
    elev = np.arcsin((r * np.cos(g) - R_E) / L)
    # station-centred azimuth: along-track angle w*t, cross-track angle g0
    north = np.sin(w * t) * 1.0
    east = np.tan(g0) * np.cos(w * t) if g0 > 1e-9 else np.zeros_like(t)
    az = np.arctan2(east * np.ones_like(t), north)
    return t, elev, L, az
