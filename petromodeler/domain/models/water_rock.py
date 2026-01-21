"""Water-Rock reaction model (开放系统水岩反应).

Provided summary indicates an open-system exchange model. We treat N (fluid/rock ratio)
作为控制变量，给定 N 计算岩石最终浓度 C_r^f 与稳定同位素 δ_r^f。

From summary:
- N = (1/D) * ln[(C_w^i - C_r^i D)/(C_w^i - C_r^f D)]
  => solve for C_r^f:
     C_r^f = (C_w^i - (C_w^i - C_r^i D)*exp(-N D)) / D
- δ_r^f = (δ_w^i + Δ) - exp(-N) * (δ_w^i - δ_r^i + Δ)

Control variable: N (usually 0-3)
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

import numpy as np

from ..common.types import ControlGrid, ControlVarType
from ..parameters.keys import ParamKey
from ..parameters.specs import DerivedSpec, ParameterSpec, UISchema
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_float, infer_group_id, make_key


class WaterRockModel(IModel):
    MODEL_ID = "water_rock"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="Water-Rock (水岩反应)", control_var=ControlVarType.N)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> UISchema:
        specs: List[ParameterSpec] = []
        derived: List[DerivedSpec] = []

        # Grid N
        specs.extend(
            [
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "N_min"),
                    label="N 最小值",
                    kind="float",
                    default=0.0,
                    min_value=0.0,
                    max_value=50.0,
                    step=0.01,
                    group="Grid",
                    help="流体/岩石比 N（常用 0-3）",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "N_max"),
                    label="N 最大值",
                    kind="float",
                    default=3.0,
                    min_value=0.0,
                    max_value=50.0,
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
            ]
        )

        # Element parameters (rock/fluid initial + D)
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                elem = q.element
                specs.extend(
                    [
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "rock", qid, "Cr_i"),
                            label=f"{elem} 岩石初始浓度 Cr_i",
                            kind="float",
                            default=100.0,
                            min_value=0.0,
                            step=0.1,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "fluid", qid, "Cw_i"),
                            label=f"{elem} 流体初始浓度 Cw_i",
                            kind="float",
                            default=200.0,
                            min_value=0.0,
                            step=0.1,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "global", qid, "D"),
                            label=f"{elem} 分配系数 D",
                            kind="float",
                            default=1.4,
                            min_value=0.0,
                            step=0.01,
                            group="Element params",
                        ),
                    ]
                )

        # Stable isotope (delta) parameters
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue) or q.kind != "delta":
                continue
            qid = quantity_id(q)

            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "rock", qid, "delta_r_i"),
                    label=f"{q.symbol} 岩石初始 δ_r^i (‰)",
                    kind="float",
                    default=0.0,
                    step=0.1,
                    group="Isotope params",
                )
            )
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "fluid", qid, "delta_w_i"),
                    label=f"{q.symbol} 流体初始 δ_w^i (‰)",
                    kind="float",
                    default=0.0,
                    step=0.1,
                    group="Isotope params",
                )
            )

            mode_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta_mode")
            specs.append(
                ParameterSpec(
                    key=mode_key,
                    help=(
                        "温度方程：1000 ln(α) = A*(1e6/T^2) + B*(1e3/T) + C\n"
                        "Δ(‰) = 1000 ln(α)；T：温度（K）；A/B/C：经验系数"
                    ),
                    label=f"{q.symbol} Δ 输入方式",
                    kind="choice",
                    choices=["Direct Δ(‰)", "From T-equation"],
                    default="Direct Δ(‰)",
                    group="Isotope params",
                )
            )

            delta_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta")
            specs.append(
                ParameterSpec(
                    key=delta_key,
                    label=f"{q.symbol} Δ (‰)",
                    kind="float",
                    default=-8.4,
                    step=0.1,
                    group="Isotope params",
                    visible_if=(mode_key.to_string(), ["Direct Δ(‰)"]),
                )
            )

            # T-equation inputs
            A_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "A")
            B_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "B")
            C_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "C")
            T_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "T")
            specs.extend(
                [
                    ParameterSpec(
                        key=T_key,
                        label=f"{q.symbol} 温度 T (K)",
                        kind="float",
                        default=873.15,
                        step=1.0,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=A_key,
                        label="系数 A",
                        kind="float",
                        default=0.0,
                        step=0.01,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=B_key,
                        label="系数 B",
                        kind="float",
                        default=0.0,
                        step=0.01,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=C_key,
                        label="系数 C",
                        kind="float",
                        default=0.0,
                        step=0.01,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                ]
            )

            derived.append(
                DerivedSpec(
                    output_key=ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta_preview"),
                    label=f"{q.symbol} 计算得到的 Δ (‰)",
                    fn="fractionation_from_temperature:Delta",
                    input_keys=[A_key.to_string(), B_key.to_string(), C_key.to_string(), T_key.to_string()],
                    unit="‰",
                    group="Isotope params",
                )
            )

        return UISchema(specs=specs, derived=derived)

    def simulate(self, requested_quantities: Set[Quantity], params: Dict[str, Any], grid: ControlGrid) -> SimulationResult:
        if grid.var != ControlVarType.N:
            raise ValueError("WaterRockModel requires ControlGrid var=N")

        group_id = infer_group_id(params, self.MODEL_ID)
        N = np.asarray(grid.values, dtype=float)

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        # Element outputs (rock final concentration)
        for q in requested_quantities:
            if not isinstance(q, ElementConc):
                continue
            qid = quantity_id(q)
            Cr_i = get_float(params, make_key(group_id, self.MODEL_ID, "rock", qid, "Cr_i"))
            Cw_i = get_float(params, make_key(group_id, self.MODEL_ID, "fluid", qid, "Cw_i"))
            D = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "D"), 1.4)

            # Cr_f = (Cw_i - (Cw_i - Cr_i D)*exp(-N D)) / D
            series_map[q] = (Cw_i - (Cw_i - Cr_i * D) * np.exp(-N * D)) / D

        # Stable isotope outputs (rock final delta)
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue) or q.kind != "delta":
                continue
            qid = quantity_id(q)
            delta_r_i = get_float(params, make_key(group_id, self.MODEL_ID, "rock", qid, "delta_r_i"), 0.0)
            delta_w_i = get_float(params, make_key(group_id, self.MODEL_ID, "fluid", qid, "delta_w_i"), 0.0)

            mode = params.get(make_key(group_id, self.MODEL_ID, "global", qid, "Delta_mode"), "Direct Δ(‰)")
            if mode == "From T-equation":
                A = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "A"), 0.0)
                B = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "B"), 0.0)
                C = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "C"), 0.0)
                T = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "T"), 873.15)
                from ..parameters.derived import fractionation_from_temperature

                _, Delta = fractionation_from_temperature(A, B, C, T)
            else:
                Delta = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "Delta"), -8.4)

            # δ_r^f = (δ_w^i + Δ) - exp(-N) * (δ_w^i - δ_r^i + Δ)
            series_map[q] = (delta_w_i + Delta) - np.exp(-N) * (delta_w_i - delta_r_i + Delta)

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
