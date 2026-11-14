import numpy as np
from satqkd_sentinel.linkmodel import *
lk = Link()
print("theta_w urad", lk.theta_w*1e6, "Y0", lk.y0())
for e in (90, 20):
    L = slant_range(np.radians(e), 500e3)
    print(e, "L km", L/1e3, "loss", lk.loss_db(L, np.radians(e)), lk.components_db(L, np.radians(e)),
          "R kbit/s", lk.rate(lk.eta(L, np.radians(e)))[0]/1e3, "QBER %", 100*lk.rate(lk.eta(L, np.radians(e)))[1])
print("limit dB", lk.loss_limit_db())
for sj in (10e-6, 20e-6):
    print("pointing dB", sj, -10*np.log10(lk.with_(sigma_j=sj).eta_pt()))
for em in (25, 30, 40, 60, 90):
    t, el, L, az = pass_profile(np.radians(em))
    r, q = lk.rate(lk.eta(L, el))
    print(em, "T", t[-1]-t[0], "minloss", lk.loss_db(L, el).min(), "maxR", r.max()/1e3, "Kinf Mbit", r.sum()/1e6)
