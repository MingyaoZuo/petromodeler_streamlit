"""Simulation result object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

from .common.types import ControlGrid, NumericArray
from .quantities import Quantity


@dataclass
class SimulationResult:
    grid: ControlGrid
    series_map: Dict[Quantity, NumericArray]
    warnings: list[str] = field(default_factory=list)

    def get_series(self, q: Quantity) -> NumericArray:
        return np.asarray(self.series_map[q], dtype=float)
