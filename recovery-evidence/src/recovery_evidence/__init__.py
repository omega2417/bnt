"""Recovery-evidence verification under limited audit capacity.

Reference implementation and reproduction package for the simulation study
"Prioritizing Recovery Evidence Verification across Shared Service
Dependencies under Limited Audit Capacity".

Layering (see docs/ARCHITECTURE.md):

* ``topology``   - dependency maps, readiness functions, influence measures
* ``policies``   - verification policies P0-P3 (operator-visible inputs only)
* ``generator``  - exogenous hidden trajectories and notices (NumPy PCG64)
* ``simulation`` - operator, guarded test module and evaluator
* ``experiment`` - the 13 conditions and the primary logs
* ``analysis``   - independent re-computation from the logs (no simulator import)
* ``figures``    - Figures 1-5 in journal formats
* ``checks``     - the 27 implementation checks of Section 4.6
"""

__version__ = "1.0.0"
ROOT_ENTROPY = 20261123
ANALYSIS_SEED = 20261124
