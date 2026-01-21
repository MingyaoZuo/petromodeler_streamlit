"""Simulation result object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

import numpy as np

from .common.types import ControlGrid, NumericArray
from .quantities import Quantity


@dataclass
class SimulationResult:
    grid: ControlGrid
    series_map: Dict[Quantity, NumericArray]
    detail_table: Optional[Any] = None  # typically a pandas DataFrame in application layer
    warnings: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_series(self, q: Quantity) -> NumericArray:
        return np.asarray(self.series_map[q], dtype=float)
