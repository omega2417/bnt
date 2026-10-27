"""crtm — Cyber-Resilience Tuple Model.

Reference implementation accompanying the article
"A Set-Theoretic Tuple Model with Level-Consistent Normalization and
Non-Compensatory Aggregation for Assessing the Cyber Resilience of
Critical Infrastructure" (Information, MDPI).
"""
from .scale import Y, LEVEL_NAMES, LEVEL_ABBR, level, level_abbr, level_name, band
from .normalization import ClassTable, ClassTableError, grid_check, is_consistent
from .aggregation import additive, gate, hard_gate, power, capped, missing_enclosure
from .hierarchy import (TASKS, GOALS, TECHNIQUES, Projection, iota, iota_inv, check_code,
                        jaccard_distance, jaccard_index, poset_size)
from .metrics import Metric, Action, load_metrics, load_scenarios, DATA_DIR
from .evaluation import evaluate_action, evaluate_scenario, score_vector, dominates
from .uncertainty import dirichlet_moments, sample_scores, SEED, N_SAMPLES

__version__ = "1.0.0"
