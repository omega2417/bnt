import csv, json, statistics
from collections import defaultdict, Counter
D='runs/reference_20260730/'
# truth
cls_count=Counter(); truth_ids={}; frames=set(); tick_per_sc=defaultdict(set)
vmin=1e9; vmax=-1e9; zmin=1e9; zmax=-1e9
truth_rows=0
with open(D+'radartwin_truth.csv') as f:
    r=csv.reader(f); next(r)
    for v in r:
        truth_rows+=1
        sc=int(v[0]); tk=int(v[1]); tid=int(v[3]); c=int(v[4])
        z=float(v[7]); vx=float(v[8]); vy=float(v[9]); vz=float(v[10])
        sp=(vx*vx+vy*vy+vz*vz)**0.5
        vmin=min(vmin,sp); vmax=max(vmax,sp); zmin=min(zmin,z); zmax=max(zmax,z)
        if tid not in truth_ids: truth_ids[tid]=c; cls_count[c]+=1
        frames.add((sc,tk)); tick_per_sc[sc].add(tk)
# max simultaneous: per (scenario,tick) count distinct truth ids
copresent=defaultdict(int)
with open(D+'radartwin_truth.csv') as f:
    r=csv.reader(f); next(r)
    for v in r: copresent[(int(v[0]),int(v[1]))]+=1
maxsim=max(copresent.values())
# measurements: SNR, completeness range
smin=1e9; smax=-1e9; cmin=1e9; cmax=-1e9; azmin=1e9; azmax=-1e9
with open(D+'radartwin_measurements.csv') as f:
    r=csv.reader(f); next(r)
    for v in r:
        if int(v[3])<0: continue
        snr=float(v[8]); comp=float(v[10]); az=float(v[5])
        smin=min(smin,snr); smax=max(smax,snr); cmin=min(cmin,comp); cmax=max(cmax,comp)
        azmin=min(azmin,az); azmax=max(azmax,az)
# scenarios json: maneuver types, kinds
js=json.load(open(D+'radartwin_scenarios.json'))
maneuvers=Counter(); kinds=Counter(); speeds=[]; alts=[]
for s in js['scenarios']:
    kinds[s['kind']]+=1
    for o in s['objects']:
        maneuvers[o['maneuver']]+=1; speeds.append(o['speed_mps']); alts.append(o['cruise_alt_m'])
tot=sum(cls_count.values())
CN={0:'UAV',1:'BIRD',2:'OTHER'}
print("scenarios:", js['num_scenarios'])
print("scenario kinds:", dict(kinds))
print("distinct truth trajectories:", len(truth_ids))
print("total truth rows:", truth_rows)
print("distinct frames (scenario,tick):", len(frames))
print("class counts:", {CN[k]:v for k,v in cls_count.items()}, "ratio:", {CN[k]:round(v/tot,3) for k,v in cls_count.items()})
print("max simultaneous targets:", maxsim)
print(f"speed range (truth inst): {vmin:.1f}..{vmax:.1f} m/s ; nominal cruise speeds {min(speeds):.1f}..{max(speeds):.1f}")
print(f"altitude range: {zmin:.1f}..{zmax:.1f} m ; nominal cruise alt {min(alts):.1f}..{max(alts):.1f}")
print(f"SNR range (true det): {smin:.1f}..{smax:.1f} dB")
print(f"completeness range (true det): {cmin:.2f}..{cmax:.2f}")
print(f"azimuth range: {azmin:.1f}..{azmax:.1f} deg")
print("maneuver types:", dict(maneuvers))
print("update rate: 10 Hz (dt=0.1 s)")
