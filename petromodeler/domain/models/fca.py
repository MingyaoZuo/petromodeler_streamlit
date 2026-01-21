"""FCA model (Decoupled Assimilation–Fractional Crystallization / 解耦同化-分离结晶).

Based on provided summary:
- Cf = C0 * F^(D-1)
- Mc = 1 - (F - r)/(1 - r)
- Element:
    C_l = (Ca*r*Mc + Cf*(1-Mc)) / F
- Isotope (ratio):
    IC_l = (ICa*Ca*r*Mc + IC0*Cf*(1-Mc)) / (C_l * F)

Control variable: F (0,1]
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

import numpy as np

from ..common.errors import ModelComputationError
from ..common.types import ControlGrid, ControlVarType
from ..parameters.grid import control_grid_specs
from ..parameters.keys import ParamKey
from ..parameters.specs import ParameterSchema, ParameterSpec
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_float, make_key


class FCAModel(IModel):
    MODEL_ID = "fca"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="FCA (解耦同化-分离结晶)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        specs: List[ParameterSpec] = []

        specs.extend(control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F))

        # global r
        specs.append(
            ParameterSpec(
                key=ParamKey(group_id, self.MODEL_ID, "global", "", "r"),
                label="r = m_a / m_c",
                kind="float",
                default=0.2,
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                group="Global",
                help="注意：r 不能等于 1",
            )
        )

        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                elem = q.element
                specs.extend(
                    [
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "C0"),
                            label=f"{elem} 初始浓度 C0",
                            kind="float",
                            default=100.0,
                            min_value=0.0,
                            step=10.0,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "assimilant", qid, "Ca"),
                            label=f"{elem} 同化物质浓度 Ca",
                            kind="float",
                            default=200.0,
                            min_value=0.0,
                            step=10.0,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "partition", qid, "D"),
                            label=f"{elem} 总分配系数 D",
                            kind="float",
                            default=1.0,
                            min_value=0.0,
                            step=0.01,
                            group="Element params",
                        ),
                    ]
                )

            elif isinstance(q, IsotopeValue):
                qid = quantity_id(q)
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "IC0"),
                        label=f"{q.symbol} 初始值",
                        kind="float",
                        default=0.703 if q.kind == "ratio" else 0.0,
                        step=0.1,
                        group="Isotope params",
                    )
                )
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "assimilant", qid, "ICa"),
                        label=f"{q.symbol} 同化端元值",
                        kind="float",
                        default=0.710 if q.kind == "ratio" else 0.0,
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
            raise ValueError("FCAModel requires a ControlGrid with var=F")

        F = np.asarray(grid.values, dtype=float)

        r = get_float(params, make_key(group_id, self.MODEL_ID, "global", "", "r"))
        if abs(r - 1.0) < 1e-12:
            raise ModelComputationError("FCA: r cannot be 1")

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        # element series first
        for q in requested_quantities:
            if not isinstance(q, ElementConc):
                continue
            qid = quantity_id(q)
            C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "C0"))
            Ca = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", qid, "Ca"))
            D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))

            Cf = C0 * np.power(F, (D - 1.0))
            Mc = 1.0 - (F - r) / (1.0 - r)
            C_l = (Ca * r * Mc + Cf * (1.0 - Mc)) / F
            series_map[q] = C_l

        # isotope values
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            IC0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC0"))
            ICa = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", qid, "ICa"))

            carrier = q.carrier
            if not carrier:
                warnings.append(f"FCA: isotope {q.symbol} missing carrier element; returning NaN")
                series_map[q] = np.full_like(F, np.nan)
                continue

            conc_qid = f"conc:melt:{carrier}"
            C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", conc_qid, "C0"), np.nan)
            Ca = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", conc_qid, "Ca"), np.nan)
            D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", conc_qid, "D"), np.nan)

            Cf = C0 * np.power(F, (D - 1.0))
            Mc = 1.0 - (F - r) / (1.0 - r)
            # need C_l for carrier
            C_l = (Ca * r * Mc + Cf * (1.0 - Mc)) / F

            # as given
            num = ICa * Ca * r * Mc + IC0 * Cf * (1.0 - Mc)
            den = C_l * F
            series_map[q] = num / den

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
