import json, numpy as np
from satqkd_sentinel.linkmodel import *
from satqkd_sentinel.geo import *
gs = [(48.46, 35.05), (28.30, -16.51)]
rows = {}
lat = np.radians(np.linspace(-89, 89, 357)); lon = np.radians(np.linspace(-180, 180, 721)); LON, LAT = np.meshgrid(lon, lat)
for n in (3, 4, 6):
    c = coverage_stats(n)
    cp = contact_plan(n, gs, hours=240, dt=10.0)
    k = cp["geo"].sum(0)
    kh = sum((central_angle(LAT, LON, ls) <= coverage_angle(0.0)) for ls in slots(n))
    rows[n] = dict(chord=isl_chord(n)/1e3, delay=isl_chord(n)/C_LIGHT*1e3, s1=100*c["share1"], s2=100*c["share2"], latc=c["lat_cont"],
                   r1=100*(k >= 1).mean(), r2=100*(k >= 2).mean(), per=100*cp["geo"].mean(), maxhor=int(kh.max()), minhor=int(kh.min()))
    print(n, rows[n])
cp = contact_plan(4, gs, hours=240, dt=5.0)
for i, m in enumerate(cp["site"]):
    st = np.flatnonzero(np.diff(m.astype(int)) == 1)
    print("site", i, "share %", 100*m.mean(), "passes/day", len(st)/10, "min/day", m.sum()*5/60/10)
# OPA footprint with the article's field of regard (Section 4.1)
chip = np.degrees(np.arcsin(1.55/4.0))
for d in (0.1, 1.0):
    M = d/(4096*2e-6); half = chip/M
    print(d, "M", M, "half FoR deg", half, "radius km", H_GEO*np.tan(np.radians(half))/1e3)
print("Earth disc", np.degrees(np.arcsin(R_E/R_GEO)), "psi0", np.degrees(coverage_angle(0.0)))
import os, sys; out = sys.argv[1] if len(sys.argv) > 1 else "results/geo_table.json"; os.makedirs(os.path.dirname(out) or ".", exist_ok=True); json.dump(rows, open(out, "w"), indent=1)
