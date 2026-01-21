"""Application-level result view models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..domain.common.types import ControlGrid, NumericArray
from ..domain.quantities import Quantity
from ..domain.results import SimulationResult


@dataclass
class GroupRunResult:
    """A simulated group plus application presentation/export data."""

    domain_result: SimulationResult
    detail_table: pd.DataFrame
    x_label: str
    y_label: str
    model_id: str
    group_id: str

    @property
    def grid(self) -> ControlGrid:
        return self.domain_result.grid

    @property
    def series_map(self) -> dict[Quantity, NumericArray]:
        return self.domain_result.series_map

    @property
    def warnings(self) -> list[str]:
        return self.domain_result.warnings
