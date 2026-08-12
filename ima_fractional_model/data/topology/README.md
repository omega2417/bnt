# Topology

`build_topology.py` regenerates `config/ima_22node.yaml` (the synthetic 22-node
IMA graph: 8 CPM / 4 SW / 10 RDC, DAL A/B/C = 4/8/10, dual-homed CPMs, switch
ring with a cross-link) deterministically from a fixed seed.

    python data/topology/build_topology.py
