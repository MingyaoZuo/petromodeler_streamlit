"""FC model (Fractional crystallization / 分离结晶).

Formulas (based on provided summary):
- Element concentration:
    C_l = C0 * F^(D - 1)
- Isotope value (ratio/delta/epsilon):
    IC_l = IC0 (constant)

Notes
-----
- This implementation treats isotopic values as "conservative" during FC.
- The control variable is residual melt fraction F in (0, 1].
"""

from __future__ import annotations

from typing import Any, Dict, Set

import numpy as np

from ..common.types import ControlGrid, ControlVarType
from ..parameters.grid import control_grid_specs
from ..parameters.keys import ParamKey
from ..parameters.specs import ParameterSchema, ParameterSpec
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_float, make_key


class FCModel(IModel):
    MODEL_ID = "fc"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="FC (分离结晶)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        specs: list[ParameterSpec] = []

        specs.extend(control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F))

        # Per requested quantity
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                elem = q.element
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "C0"),
                        label=f"{elem} 初始浓度 C0",
                        kind="float",
                        default=100.0,
                        min_value=0.0,
                        step=10.0,
                        group="Element params",
                    )
                )
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "partition", qid, "D"),
                        label=f"{elem} 总分配系数 D",
                        kind="float",
                        default=1.0,
                        min_value=0.0,
                        step=0.01,
                        group="Element params",
                    )
                )

            elif isinstance(q, IsotopeValue):
                qid = quantity_id(q)
                default_val = 0.703 if q.kind == "ratio" else 0.0
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "IC0"),
                        label=f"{q.symbol} 初始值",
                        kind="float",
                        default=default_val,
                        step=0.1,
                        group="Isotope params",
                    )
                )

        return ParameterSchema(specs=specs, derived=[])

    def simulate(
        self,
        requested_quantities: Set[Quantity],
        group_id: str,
        params: Dict[str, Any],
        grid: ControlGrid,
    ) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("FCModel requires a ControlGrid with var=F")

        F = np.asarray(grid.values, dtype=float)

        series_map: Dict[Quantity, np.ndarray] = {}

        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "C0"))
                D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))
                series_map[q] = C0 * np.power(F, (D - 1.0))

            elif isinstance(q, IsotopeValue):
                qid = quantity_id(q)
                IC0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC0"))
                series_map[q] = np.full_like(F, IC0, dtype=float)

        return SimulationResult(grid=grid, series_map=series_map)
