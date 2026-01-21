"""Rayleigh fractionation model (脱挥发份 / Rayleigh分馏).

From provided summary:
- Element: C_f = C_i * F^(D-1)
- Stable isotope (delta): δ_f = δ_i + 1000 * (F^(alpha-1) - 1)

Control variable: F in (0,1]
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


class RayleighModel(IModel):
    MODEL_ID = "rayleigh"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="Rayleigh (脱挥发份)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> UISchema:
        specs: List[ParameterSpec] = []
        derived: List[DerivedSpec] = []

        # Grid F
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

        # Element parameters
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                elem = q.element
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "Ci"),
                        label=f"{elem} 初始浓度 Ci",
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
                        label=f"{elem} 分配系数 D (矿物/流体)",
                        kind="float",
                        default=1.0,
                        min_value=0.0,
                        step=0.01,
                        group="Element params",
                    )
                )

        # Isotope delta parameters
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            # only delta is supported by the provided formula
            if q.kind != "delta":
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "IC0"),
                        label=f"{q.symbol} 初始值",
                        kind="float",
                        default=0.0,
                        step=0.01,
                        group="Isotope params",
                        help="Rayleigh 模型中非 δ 类型仅作为常数输出",
                    )
                )
                continue

            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "delta_i"),
                    label=f"{q.symbol} 初始 δ_i (‰)",
                    kind="float",
                    default=0.0,
                    step=0.1,
                    group="Isotope params",
                )
            )

            mode_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "alpha_mode")
            specs.append(
                ParameterSpec(
                    key=mode_key,
                    help=(
                        "温度方程：1000 ln(α) = A*(1e6/T^2) + B*(1e3/T) + C\n"
                        "T：温度（K）；A/B/C：经验系数；α = exp((1000 ln(α))/1000)"
                    ),
                    label=f"{q.symbol} α 输入方式",
                    kind="choice",
                    choices=["Direct α", "From T-equation"],
                    default="Direct α",
                    group="Isotope params",
                )
            )

            alpha_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "alpha")
            specs.append(
                ParameterSpec(
                    key=alpha_key,
                    label=f"{q.symbol} α",
                    kind="float",
                    default=1.00833,
                    step=0.00001,
                    group="Isotope params",
                    visible_if=(mode_key.to_string(), ["Direct α"]),
                )
            )

            # Temperature equation parameters
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
                    output_key=ParamKey(group_id, self.MODEL_ID, "global", qid, "alpha_preview"),
                    label=f"{q.symbol} 计算得到的 α",
                    fn="fractionation_from_temperature:alpha",
                    input_keys=[A_key.to_string(), B_key.to_string(), C_key.to_string(), T_key.to_string()],
                    unit="",
                    group="Isotope params",
                )
            )

        return UISchema(specs=specs, derived=derived)

    def simulate(self, requested_quantities: Set[Quantity], params: Dict[str, Any], grid: ControlGrid) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("RayleighModel requires ControlGrid var=F")

        group_id = infer_group_id(params, self.MODEL_ID)
        F = np.asarray(grid.values, dtype=float)

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                Ci = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "Ci"))
                D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))
                series_map[q] = Ci * np.power(F, (D - 1.0))

        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            if q.kind != "delta":
                IC0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC0"), 0.0)
                series_map[q] = np.full_like(F, IC0)
                continue

            delta_i = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "delta_i"), 0.0)
            mode = params.get(make_key(group_id, self.MODEL_ID, "global", qid, "alpha_mode"), "Direct α")
            if mode == "From T-equation":
                A = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "A"), 0.0)
                B = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "B"), 0.0)
                C = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "C"), 0.0)
                T = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "T"), 873.15)
                from ..parameters.derived import fractionation_from_temperature

                alpha, _ = fractionation_from_temperature(A, B, C, T)
            else:
                alpha = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "alpha"), 1.00833)

            series_map[q] = delta_i + 1000.0 * (np.power(F, (alpha - 1.0)) - 1.0)

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
