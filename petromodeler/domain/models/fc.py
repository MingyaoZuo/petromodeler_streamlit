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
from ..parameters.keys import ParamKey
from ..parameters.specs import ParameterSpec, UISchema
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_bool, get_float, get_int, infer_group_id, make_key


class FCModel(IModel):
    MODEL_ID = "fc"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="FC (分离结晶)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> UISchema:
        specs: list[ParameterSpec] = []

        # Grid (F)
        specs.extend(
            [
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "F_min"),
                    label="F 最小值",
                    kind="float",
                    default=0.05,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.01,
                    help="残余熔体分数 F (0-1]",
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "F_max"),
                    label="F 最大值",
                    kind="float",
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.01,
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "n_points"),
                    label="点数",
                    kind="int",
                    default=50,
                    min_value=2,
                    max_value=2000,
                    step=1,
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "descending"),
                    label="F 从大到小",
                    kind="bool",
                    default=True,
                    group="Grid",
                ),
            ]
        )

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
                        step=0.1,
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
                        step=0.001,
                        group="Isotope params",
                    )
                )

        return UISchema(specs=specs, derived=[])

    def simulate(self, requested_quantities: Set[Quantity], params: Dict[str, Any], grid: ControlGrid) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("FCModel requires a ControlGrid with var=F")

        group_id = infer_group_id(params, self.MODEL_ID)
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
