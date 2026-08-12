import yaml, numpy as np

# ---- Node definition: 8 CPM, 4 SW, 10 RDC = 22 nodes ----
# DAL A(4) = CPM1-4 ; DAL B(8) = CPM5-8 + SW1-4 ; DAL C(10) = RDC1-10
rng = np.random.default_rng(20240601)

nodes = []
def add(nid, ntype, dal):
    prio = {'A':3,'B':2,'C':1}[dal]
    r    = {'A':1.6,'B':0.6,'C':0.25}[dal]
    lam  = float(rng.uniform(0.25, 0.35))
    nodes.append(dict(node_id=nid, node_type=ntype, dal=dal, priority=prio,
                      criticality_weight_raw={'A':3.0,'B':2.0,'C':1.0}[dal],
                      service_capacity=1.1, recovery_rate=0.6,
                      reconfiguration_rate=r, traffic_arrival=lam))

for i in range(1,5):  add(f'CPM{i}','CPM','A')   # DAL-A on CPM1-4
for i in range(5,9):  add(f'CPM{i}','CPM','B')
for i in range(1,5):  add(f'SW{i}','SW','B')
for i in range(1,11): add(f'RDC{i}','RDC','C')

# normalize criticality weights to sum 1
tot = sum(n['criticality_weight_raw'] for n in nodes)
for n in nodes:
    n['criticality_weight'] = round(n['criticality_weight_raw']/tot, 6)
    del n['criticality_weight_raw']

ids = [n['node_id'] for n in nodes]

# ---- Edges: directed dependency j->i (i depends on j) ----
edges = []
def edge(src, dst, w, delay, spill=0.04):
    edges.append(dict(source=src, destination=dst,
                      dependency_weight=round(float(w),4),
                      degradation_propagation_coeff=0.256,  # per-edge base beta (Table 1 nominal 0.25; fine-tuned to Tcat~101)
                      backlog_spillover_coeff=spill,
                      communication_delay=round(float(delay),3)))

def dly():  # dimensionless delays in [0.3, 4.0] (physical 0.5-3 ms)
    return float(rng.uniform(0.3, 1.6))

# Switch ring (bidirectional) + one cross-link
ring = [('SW1','SW2'),('SW2','SW3'),('SW3','SW4'),('SW4','SW1')]
for a,b in ring:
    edge(a,b, rng.uniform(0.7,0.9), dly()); edge(b,a, rng.uniform(0.7,0.9), dly())
edge('SW1','SW3', 0.6, dly()); edge('SW3','SW1', 0.6, dly())   # cross-link

# CPMs dual-homed: each CPM attaches to two switches (bidirectional data path)
cpm_homes = {
 'CPM1':('SW1','SW2'),'CPM2':('SW2','SW3'),'CPM3':('SW3','SW4'),'CPM4':('SW4','SW1'),
 'CPM5':('SW1','SW3'),'CPM6':('SW2','SW4'),'CPM7':('SW3','SW1'),'CPM8':('SW4','SW2')}
for cpm,(s1,s2) in cpm_homes.items():
    # DAL-A CPMs (1-4) are insulated by redundant dual-homing / voting, so a single
    # degraded switch corrupts them only weakly; DAL-B CPMs are more exposed.
    w = 0.9 if int(cpm[3])<=4 else 0.8
    edge(s1, cpm, w, dly()); edge(cpm, s1, 0.5, dly())
    edge(s2, cpm, w, dly()); edge(cpm, s2, 0.5, dly())

# RDCs feed sensor data into switches (RDC -> SW): degradation & backlog propagate upward
rdc_homes = {**{f'RDC{i}':'SW1' for i in (1,2,3)},
             **{f'RDC{i}':'SW2' for i in (4,5,6)},
             **{f'RDC{i}':'SW3' for i in (7,8)},
             **{f'RDC{i}':'SW4' for i in (9,10)}}
for rdc,sw in rdc_homes.items():
    edge(rdc, sw, rng.uniform(0.6,0.8), dly())
    edge(sw, rdc, 0.3, dly())   # weak downstream (commands)

# CPM-CPM partition data dependencies (functional chains toward DAL-A)
for a,b in [('CPM5','CPM1'),('CPM6','CPM2'),('CPM7','CPM3'),('CPM8','CPM4'),
            ('CPM2','CPM1'),('CPM3','CPM4')]:
    edge(a,b, rng.uniform(0.5,0.7), dly())

# ---- Contention sets H_i: higher-priority nodes sharing a CPM/switch port ----
# Approx: nodes sharing a switch attachment; higher priority blocks lower.
config = dict(
    meta=dict(name='synthetic_22node_IMA', n_nodes=22,
              node_counts=dict(CPM=8, SW=4, RDC=10),
              dal_counts=dict(A=4, B=8, C=10),
              note='Synthetic mechanism-oriented research architecture. '
                   'NOT calibrated to any real Airbus/Boeing/certified IMA platform.'),
    global_params=dict(
        mu=0.6, gamma=0.15, eta=0.22, theta=0.4, delta=0.3,
        beta_base=0.256, spillover=0.04,
        recon_kappa=14.0, recon_nu=0.35,
        x_cat=0.6, alpha=0.8, beta_order=0.8,
        xi_ref=0.55, comparison_gamma_factor=1.9218),
    nodes=nodes,
    edges=edges)

with open('config/ima_22node.yaml','w') as f:
    yaml.safe_dump(config, f, sort_keys=False, default_flow_style=False)
print('nodes', len(nodes), 'edges', len(edges))
print('DAL counts', {d:sum(1 for n in nodes if n['dal']==d) for d in 'ABC'})
