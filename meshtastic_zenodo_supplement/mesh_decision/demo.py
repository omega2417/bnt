"""Generate synthetic examples, never field measurements."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
from .schema import COLUMNS, FEATURES, TARGET, write_csv

def generate(folder, seed=42, groups=90, per_group=40):
    if groups < 12 or per_group < 4:
        raise ValueError("demo requires at least 12 groups and four events per group")
    rng = np.random.default_rng(seed); rows = []
    for g in range(groups):
        scenario = g % 9
        radio_shift = rng.normal(0, 3)
        for i in range(per_group):
            t = datetime(2026, 10, 1, tzinfo=timezone.utc)+timedelta(days=g, seconds=i*360)
            rssi = np.clip(rng.normal(-109, 12)+radio_shift, -143, -40)
            snr = np.clip((rssi+114)*.45+rng.normal(0, 3), -25, 20)
            pdr = np.clip(1/(1+np.exp(-(snr+7)/5))+rng.normal(0,.07), .02, .99)
            terminal = int(not (scenario == 4 or rng.random()<.04))
            s0 = int(not (scenario == 5 or rng.random()<.03))
            battery = rng.uniform(8,100) if scenario != 6 else rng.uniform(0,20)
            backup = rng.uniform(10,360) if scenario not in {1,3,8} else rng.uniform(0,90)
            q = int(rng.integers(0,15)); remain = rng.uniform(30,300)
            latency = np.clip(8+80*(1-pdr)+q*1.3+rng.exponential(8), 0, 300)
            aoi = np.clip(rng.exponential(30)+110*(1-pdr), 0, 900)
            hops = int(rng.integers(1,3)); internet = int(scenario not in {2,3})
            z = (4.2*(pdr-.55)+.055*snr-.018*latency-.012*aoi+
                 .008*battery+.003*backup-.10*q-.25*(hops-1)+
                 .012*(remain-120)+2.5*(terminal-1)+2.5*(s0-1))
            # Invented probabilistic mechanism for a software demonstration only.
            probability = 1/(1+np.exp(-z))
            values = [rssi,snr,pdr,latency,aoi,battery,backup,q,hops,terminal,s0,internet,remain]
            row = dict(zip(FEATURES, [round(float(v),6) for v in values]))
            row.update(event_id=f"sim-{g:03d}-{i:03d}",group_id=f"sim-group-{g:03d}",
                       run_id=f"sim-run-{g:03d}",node_id="M1" if i%2 else "M2",
                       scenario=f"E{scenario}",provenance="synthetic",decision_time=t.isoformat(),
                       feature_window_end=t.isoformat(),outcome_observed_at=(t+timedelta(seconds=301)).isoformat(),
                       completed_on_time=int(rng.random()<probability))
            rows.append(row)
    folder=Path(folder)
    write_csv(folder/'synthetic_training.csv',rows,COLUMNS+[TARGET,"outcome_observed_at"])
    base=rows[0].copy();base.update(rssi_dbm=-90,snr_db=10,pdr_5m=.98,latency_p95_5m_s=15,
          aoi_s=10,battery_pct=90,backup_minutes=120,queue_depth=0,hop_count=1,
          terminal_available=1,s0_available=1,deadline_remaining_s=290)
    cases=[]
    for name, change in [
        ("healthy",{}),("terminal_off",{"terminal_available":0}),
        ("radio_off",{"s0_available":0}),("power_low",{"backup_minutes":2}),
        ("stale",{"aoi_s":200}),("expired",{"deadline_remaining_s":0}),
        ("weak_link",{"rssi_dbm":-130,"snr_db":-15,"pdr_5m":.1,"latency_p95_5m_s":90}),
        ("missing_input",{"rssi_dbm":""}),
    ]:
        row=base.copy();row.update(change);row.update(event_id="example-"+name,run_id="examples",group_id="examples")
        cases.append(row)
    write_csv(folder/'inference_examples.csv',cases,COLUMNS)
    return len(rows)
