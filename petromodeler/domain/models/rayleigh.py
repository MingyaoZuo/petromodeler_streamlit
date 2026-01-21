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
from ..parameters.grid import control_grid_specs
from ..parameters.keys import ParamKey
from ..parameters.specs import DerivedSpec, ParameterSchema, ParameterSpec
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_float, make_key


class RayleighModel(IModel):
    MODEL_ID = "rayleigh"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="Rayleigh (脱挥发份)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        specs: List[ParameterSpec] = []
        derived: List[DerivedSpec] = []

        specs.extend(control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F))

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
                        step=10.0,
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
                        step=0.1,
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

            mode_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta_mode")
            specs.append(
                ParameterSpec(
                    key=mode_key,
                    help=(
                        "温度方程：1000 ln(α) = A*(1e6/T^2) + B*(1e3/T) + C\n"
                        "Δ(‰) ≈ 1000 ln(α)；α = exp(Δ/1000)\n"
                        "T：温度（°C，后台计算时换算为 K）；A/B/C：经验系数"
                    ),
                    label=f"{q.symbol} Δ 输入方式",
                    kind="choice",
                    choices=["Direct Δ(‰)", "From T-equation"],
                    default="Direct Δ(‰)",
                    group="Isotope params",
                )
            )

            Delta_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta")
            specs.append(
                ParameterSpec(
                    key=Delta_key,
                    label=f"{q.symbol} Δ (‰)",
                    kind="float",
                    default=8.33,
                    step=0.1,
                    group="Isotope params",
                    visible_if=(mode_key.to_string(), ["Direct Δ(‰)"]),
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
                        label=f"{q.symbol} 温度 T (°C)",
                        kind="float",
                        default=600.0,
                        step=10.0,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=A_key,
                        label="系数 A",
                        kind="float",
                        default=0.0,
                        step=0.1,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=B_key,
                        label="系数 B",
                        kind="float",
                        default=0.0,
                        step=0.1,
                        group="Isotope params",
                        visible_if=(mode_key.to_string(), ["From T-equation"]),
                    ),
                    ParameterSpec(
                        key=C_key,
                        label="系数 C",
                        kind="float",
                        default=0.0,
                        step=0.1,
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

        return ParameterSchema(specs=specs, derived=derived)

    def simulate(
        self,
        requested_quantities: Set[Quantity],
        group_id: str,
        params: Dict[str, Any],
        grid: ControlGrid,
    ) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("RayleighModel requires ControlGrid var=F")

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
            mode = params.get(make_key(group_id, self.MODEL_ID, "global", qid, "Delta_mode"), "Direct Δ(‰)")
            if mode == "From T-equation":
                A = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "A"), 0.0)
                B = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "B"), 0.0)
                C = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "C"), 0.0)
                T = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "T"), 600.0)
                from ..parameters.derived import celsius_to_kelvin, fractionation_from_temperature

                _, Delta = fractionation_from_temperature(A, B, C, celsius_to_kelvin(T))
            else:
                Delta = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "Delta"), 8.33)

            alpha = np.exp(Delta / 1000.0)
            series_map[q] = delta_i + 1000.0 * (np.power(F, (alpha - 1.0)) - 1.0)

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
