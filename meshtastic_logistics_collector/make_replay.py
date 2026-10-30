"""Synthetic replay log for testing the collector without radio hardware.

3 vehicles, 6 hours, ~15 % lost positions, flood duplicates, relay telemetry and
4 critical events (one completed late, one never completed). Writes packets.jsonl
(input for `collector.py --replay`) and ops.json (planned operations for import_plan.py).
Synthetic data, NOT field measurements.
"""
import json, random
from logi_proto import new_event, reply
random.seed(1); T0=1_800_000_000; out=[]
rid=random.Random(42)  # separate RNG: deterministic event ids without shifting the main sequence
pid=1000
def pk(t, frm, port, dec, hops=1, dup=False):
    global pid
    if not dup: pid+=1
    out.append({"t":t,"packet":{"from":frm,"to":4294967295,"id":pid,"rxSnr":round(random.uniform(-12,8),1),"rxRssi":random.randint(-120,-80),
      "hopLimit":3-hops,"hopStart":3,"rxTime":int(t),"decoded":dict(portnum=port, **dec)}})
for v in (11,12,13):
    for k in range(0,36):
        t=T0+k*600+v
        if random.random()<0.85:
            pk(t,v,"POSITION_APP",{"position":{"latitudeI":484500000+k*100,"longitudeI":350400000,"satsInView":9,"time":int(t)}},hops=random.choice([1,2]))
            if random.random()<0.3: pk(t+2,v,"POSITION_APP",{"position":{"latitudeI":1,"longitudeI":1}},dup=True)
pk(T0+50,21,"TELEMETRY_APP",{"telemetry":{"deviceMetrics":{"batteryLevel":87,"voltage":4.01,"channelUtilization":4.2,"airUtilTx":1.3,"uptimeSeconds":3600}}})
ops=[]
for i,op in enumerate([501,502,503,504]):
    ev=new_event(op,1,value=85,deadline_min=30); ev.t_created=T0+1000*i+100; ev.event_id=bytes(rid.getrandbits(8) for _ in range(6))
    pk(T0+1000*i+101,11,256,{"payload_hex":ev.encode().hex()},hops=2)
    pk(T0+1000*i+160,1,256,{"payload_hex":reply(ev,2).encode().hex()})
    if i<3: pk(T0+1000*i+900 if i<2 else T0+1000*i+2500,11,256,{"payload_hex":reply(ev,3).encode().hex()},hops=2)
    ops.append((op,T0+1000*i+100+1800))
json.dump(ops,open("ops.json","w"))
with open("packets.jsonl","w") as f:
    for r in out: f.write(json.dumps(r)+"\n")
print(len(out))
