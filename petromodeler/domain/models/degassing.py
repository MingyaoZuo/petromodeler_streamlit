"""Devolatilization model preserving the original volatile-loss formulas.

C_f = Ci * F**(D-1)
delta_f = delta_i + 1000 * (F**(alpha-1) - 1)
Non-delta isotope values remain constant.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..common.types import ControlGrid, ControlVarType
from ..parameters.grid import control_grid_specs
from ..parameters.keys import ParamKey
from ..parameters.specs import ParameterSchema, ParameterSpec
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .fractionation import fractionation_alpha, fractionation_schema
from .utils import get_float, make_key


class DegassingModel(IModel):
    MODEL_ID = "degassing"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="脱挥发份", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: set[Quantity]) -> ParameterSchema:
        schema = ParameterSchema(specs=control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F))
        for q in requested_quantities:
            if not isinstance(q, ElementConc):
                continue
            qid = quantity_id(q)
            schema.specs.extend([
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "Ci"),
                    label=f"{q.element} 初始浓度 Ci",
                    kind="float", default=100.0, min_value=0.0, step=10.0, group="Element params",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "partition", qid, "D"),
                    label=f"{q.element} 分配系数 D (矿物/流体)",
                    kind="float", default=1.0, min_value=0.0, step=0.01, group="Element params",
                ),
            ])
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            schema.specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "initial", quantity_id(q), "delta_i" if q.kind == "delta" else "IC0"),
                    label=f"{q.symbol} 初始 δ_i (‰)" if q.kind == "delta" else f"{q.symbol} 初始值",
                    kind="float", default=0.0, step=0.1, group="Isotope params",
                    help="" if q.kind == "delta" else "脱挥发份模型中非 δ 类型仅作为常数输出",
                )
            )
            if q.kind == "delta":
                fractionation = fractionation_schema(group_id, self.MODEL_ID, q)
                schema.specs.extend(fractionation.specs)
                schema.derived.extend(fractionation.derived)
        return schema

    def simulate(
        self,
        requested_quantities: set[Quantity],
        group_id: str,
        params: dict[str, Any],
        grid: ControlGrid,
    ) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("DegassingModel requires ControlGrid var=F")
        F = np.asarray(grid.values, dtype=float)
        series_map: dict[Quantity, np.ndarray] = {}
        for q in requested_quantities:
            qid = quantity_id(q)
            if isinstance(q, ElementConc):
                Ci = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "Ci"))
                D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))
                series_map[q] = Ci * np.power(F, D - 1.0)
            elif isinstance(q, IsotopeValue):
                if q.kind != "delta":
                    initial = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC0"), 0.0)
                    series_map[q] = np.full_like(F, initial)
                else:
                    delta_i = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "delta_i"), 0.0)
                    alpha = fractionation_alpha(params, group_id, self.MODEL_ID, qid)
                    series_map[q] = delta_i + 1000.0 * (np.power(F, alpha - 1.0) - 1.0)
        return SimulationResult(grid=grid, series_map=series_map)
