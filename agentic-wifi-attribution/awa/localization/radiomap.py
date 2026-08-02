"""RSSI radiomap: log-distance propagation predictor per sensor (Module 4).

The radiomap here is *model-based* (log-distance path loss) rather than a raw
empirical survey, so that it is fully reproducible without shipping a survey
dataset.  In production this object would instead store per-reference-point
means, medians, quantiles, variances and MAD (prompt Module 4).  It is a
versioned, immutable statistical object; ``version`` participates in the SAR.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import PathLossConfig
from ..site import Site
from .grid import Grid


def log_distance_rssi(
    distance_m: np.ndarray, cfg: PathLossConfig
) -> np.ndarray:
    """Deterministic mean RSSI (dBm) at a given distance (no shadowing)."""
    d = np.maximum(distance_m, 1e-3)
    rssi = cfg.p0_dbm - 10.0 * cfg.path_loss_exp * np.log10(d / cfg.d0_m)
    return np.maximum(rssi, cfg.min_rssi_dbm)


@dataclass
class RadioMap:
    """Predicted mean RSSI from every sensor to every grid cell."""

    version: str
    sensor_ids: list
    mean_rssi: np.ndarray  # (n_sensors, n_cells)
    path_loss: PathLossConfig

    @classmethod
    def build(
        cls,
        site: Site,
        grid: Grid,
        cfg: PathLossConfig,
        version: str = "radiomap-synthetic-0.1.0",
        bias_db: np.ndarray | None = None,
    ) -> "RadioMap":
        """Build the immutable baseline radiomap for RSSI-capable sensors.

        ``bias_db`` optionally injects a per-sensor calibration/drift offset
        used to model temporal drift or hardware bias (prompt principle 5).
        """
        rssi_sensors = [s for s in site.sensors if s.supports_rssi]
        rows = []
        for i, s in enumerate(rssi_sensors):
            d = grid.distances_to(s.position)
            mean = log_distance_rssi(d, cfg)
            if bias_db is not None:
                mean = mean + bias_db[i]
            rows.append(mean)
        return cls(
            version=version,
            sensor_ids=[s.sensor_id for s in rssi_sensors],
            mean_rssi=np.vstack(rows),
            path_loss=cfg,
        )

    def predict_at(self, sensor_index: int, cell_index: int) -> float:
        return float(self.mean_rssi[sensor_index, cell_index])
