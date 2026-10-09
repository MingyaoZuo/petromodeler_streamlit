"""Rayleigh fractionation of instantaneous crystallizing minerals.

F is the residual melt fraction in (0, 1]. Outputs represent the mineral
formed at each F, rather than the residual melt or accumulated crystals:

C_mineral = D * Ci * F**(D-1)
R_mineral = alpha * Ri * F**(alpha-1)
delta_mineral = (delta_i + 1000) * alpha * F**(alpha-1) - 1000

alpha = R_mineral / R_melt = exp(Delta / 1000).
"""

from __future__ import annotations

from dataclasses import replace
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


class RayleighModel(IModel):
    MODEL_ID = "rayleigh"

    def spec(self) -> ModelSpec:
        return ModelSpec(
            id=self.MODEL_ID,
            name="Rayleigh (结晶矿物分馏)",
            control_var=ControlVarType.F,
            description="F 为残余熔体分数；输出为各 F 下瞬时形成的矿物组成。",
        )

    def required_schema(self, group_id: str, requested_quantities: set[Quantity]) -> ParameterSchema:
        grid_specs = control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F)
        schema = ParameterSchema(specs=[
            replace(spec, help="F 为残余熔体分数；输出瞬时矿物组成。")
            if spec.key.name in ("F_min", "F_max") else spec
            for spec in grid_specs
        ])
        for q in requested_quantities:
            qid = quantity_id(q)
            if isinstance(q, ElementConc):
                schema.specs.extend([
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "Ci"),
                        label=f"{q.element} 初始熔体浓度 Ci",
                        kind="float", default=100.0, min_value=0.0, step=10.0, group="Element params",
                    ),
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "partition", qid, "D"),
                        label=f"{q.element} 分配系数 D (矿物/熔体)",
                        kind="float", default=1.0, min_value=0.0, step=0.01, group="Element params",
                        help="D = C矿物/C熔体；输出浓度为 D·Ci·F^(D−1)。",
                    ),
                ])
            elif isinstance(q, IsotopeValue):
                schema.specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "delta_i" if q.kind == "delta" else "IC0"),
                        label=f"{q.symbol} 初始熔体 δ_i (‰)" if q.kind == "delta" else f"{q.symbol} 初始熔体值",
                        kind="float", default=0.703 if q.kind == "ratio" else 0.0, step=0.1,
                        group="Isotope params",
                        help="输入初始熔体同位素值；输出为瞬时矿物同位素值。",
                    )
                )
                # Radiogenic ratios/epsilon do not fractionate by default.
                fractionation = fractionation_schema(
                    group_id, self.MODEL_ID, q, default_delta=8.33 if q.kind == "delta" else 0.0
                )
                for spec in fractionation.specs:
                    if spec.key.name == "Delta":
                        spec = replace(spec, label=f"{q.symbol} 矿物-熔体 Δ (‰)")
                    elif spec.key.name == "Delta_mode":
                        spec = replace(
                            spec,
                            help=spec.help + "\nα = R矿物/R熔体；Δ = 0 时同位素不发生分馏。",
                        )
                    schema.specs.append(spec)
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
            raise ValueError("RayleighModel requires ControlGrid var=F")
        F = np.asarray(grid.values, dtype=float)
        if np.any(~np.isfinite(F)) or np.any((F <= 0.0) | (F > 1.0)):
            raise ValueError("RayleighModel requires 0 < F <= 1")
        series_map: dict[Quantity, np.ndarray] = {}
        for q in requested_quantities:
            qid = quantity_id(q)
            if isinstance(q, ElementConc):
                Ci = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "Ci"))
                D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))
                # Avoid 0*infinity at tiny F when the mineral excludes an element.
                series_map[q] = np.zeros_like(F) if D == 0.0 else D * Ci * np.power(F, D - 1.0)
            elif isinstance(q, IsotopeValue):
                initial_name = "delta_i" if q.kind == "delta" else "IC0"
                initial = get_float(
                    params, make_key(group_id, self.MODEL_ID, "initial", qid, initial_name),
                    0.703 if q.kind == "ratio" else 0.0,
                )
                alpha = fractionation_alpha(
                    params, group_id, self.MODEL_ID, qid, default_delta=8.33 if q.kind == "delta" else 0.0
                )
                mineral_factor = alpha * np.power(F, alpha - 1.0)
                if q.kind == "ratio":
                    series_map[q] = initial * mineral_factor
                else:
                    # Fractionate the ratio, then convert to delta (10^3) or
                    # epsilon (10^4); multiplying delta/epsilon itself is wrong.
                    scale = 10000.0 if q.kind == "epsilon" else 1000.0
                    series_map[q] = (initial + scale) * mineral_factor - scale
        return SimulationResult(grid=grid, series_map=series_map)
