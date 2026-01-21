"""Mush extraction model (晶粥提取 / 晶-熔分离).

From provided summary:
- Pure melt concentration:
    C_melt = C0 * F^(D-1)
- Crystal concentration:
    C_crystal = C0 * (1 - F^D) / (1 - F)
- Extracted melt (CL):
    CL = C_melt*(1-f_c) + C_crystal*f_c
- Residual cumulate (CR):
    CR = C_melt*f_m + C_crystal*(1-f_m)

Isotope ratio (for a given carrier element):
- IC_crystal = IC_melt + Δ
- IC_L = (IC_melt*C_melt*(1-f_c) + IC_crystal*C_crystal*f_c) / CL
- IC_R = (IC_crystal*C_crystal*(1-f_m) + IC_melt*C_melt*f_m) / CR

Control variable: F (0,1]

Context handling
----------------
Requested quantities may specify:
- context='extracted_melt': returns CL / IC_L
- context='cumulate': returns CR / IC_R
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

import numpy as np

from ..common.types import ControlGrid, ControlVarType
from ..parameters.grid import control_grid_specs
from ..parameters.keys import ParamKey
from ..parameters.specs import ParameterSchema, ParameterSpec
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id, normalize_element_symbol
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_float, make_key


class MushExtractModel(IModel):
    MODEL_ID = "mush_extract"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="Mush extraction (晶粥提取)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        specs: List[ParameterSpec] = []

        specs.extend(control_grid_specs(group_id, self.MODEL_ID, ControlVarType.F))

        # Output phase (per parameter group)
        phase_key = ParamKey(group_id, self.MODEL_ID, "global", "", "output_phase")
        specs.append(
            ParameterSpec(
                key=phase_key,
                label="输出相/计算对象",
                kind="choice",
                choices=["extracted_melt", "cumulate"],
                default="extracted_melt",
                group="Global",
                help=(
                    "extracted_melt：提取熔体（使用 f_c；当 f_c=0 时等同于纯熔体）\n"
                    "cumulate：残余堆积体（使用 f_m）"
                ),
            )
        )

        # Global f_c, f_m (shown based on output phase)
        specs.append(
            ParameterSpec(
                key=ParamKey(group_id, self.MODEL_ID, "global", "", "f_c"),
                label="f_c (提取熔体中晶体质量分数)",
                kind="float",
                default=0.1,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                group="Global",
                visible_if=(phase_key.to_string(), ["extracted_melt"]),
            )
        )
        specs.append(
            ParameterSpec(
                key=ParamKey(group_id, self.MODEL_ID, "global", "", "f_m"),
                label="f_m (堆积体中截留熔体质量分数)",
                kind="float",
                default=0.1,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                group="Global",
                visible_if=(phase_key.to_string(), ["cumulate"]),
            )
        )

        # Element params for all element conc requested and any isotope carriers
        elements_needed: Set[str] = set()
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                elements_needed.add(normalize_element_symbol(q.element))
            elif isinstance(q, IsotopeValue) and q.carrier:
                elements_needed.add(normalize_element_symbol(q.carrier))

        for elem in sorted(elements_needed):
            qid = f"conc:melt:{elem}"
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

        # Isotope params
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "IC_melt"),
                    label=f"{q.symbol} 熔体相初始值 IC_melt",
                    kind="float",
                    default=0.703 if q.kind == "ratio" else 0.0,
                    step=0.1,
                    group="Isotope params",
                )
            )
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta"),
                    label=f"{q.symbol} 晶-熔分馏 Δ (通常≈0)",
                    kind="float",
                    default=0.0,
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
            raise ValueError("MushExtractModel requires ControlGrid var=F")

        F = np.asarray(grid.values, dtype=float)

        # Backward compatibility: older projects may have output_phase="melt".
        # Treat it as extracted_melt with f_c forced to 0.0 (pure melt).
        output_phase_raw = str(params.get(make_key(group_id, self.MODEL_ID, "global", "", "output_phase"), "extracted_melt"))
        f_c = get_float(params, make_key(group_id, self.MODEL_ID, "global", "", "f_c"), 0.1)
        f_m = get_float(params, make_key(group_id, self.MODEL_ID, "global", "", "f_m"), 0.1)
        if output_phase_raw == "cumulate":
            output_phase = "cumulate"
            f_c_eff = f_c
        elif output_phase_raw == "melt":
            output_phase = "extracted_melt"
            f_c_eff = 0.0
        else:
            output_phase = "extracted_melt"
            f_c_eff = f_c

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        # Precompute concentrations by element
        conc_melt: Dict[str, np.ndarray] = {}
        conc_crystal: Dict[str, np.ndarray] = {}
        conc_L: Dict[str, np.ndarray] = {}
        conc_R: Dict[str, np.ndarray] = {}

        elements_needed: Set[str] = set()
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                elements_needed.add(normalize_element_symbol(q.element))
            elif isinstance(q, IsotopeValue) and q.carrier:
                elements_needed.add(normalize_element_symbol(q.carrier))

        for elem in elements_needed:
            base_qid = f"conc:melt:{elem}"
            C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", base_qid, "C0"))
            D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", base_qid, "D"))
            Cmelt = C0 * np.power(F, (D - 1.0))
            # avoid division by zero near F=1
            with np.errstate(divide="ignore", invalid="ignore"):
                Ccrys = C0 * (1.0 - np.power(F, D)) / (1.0 - F)
            # if F==1, use limit Ccrys ~ C0*D (from derivative) - approximate
            mask = np.isclose(F, 1.0)
            if np.any(mask):
                Ccrys[mask] = C0 * D

            CL = Cmelt * (1.0 - f_c_eff) + Ccrys * f_c_eff
            CR = Cmelt * f_m + Ccrys * (1.0 - f_m)

            conc_melt[elem] = Cmelt
            conc_crystal[elem] = Ccrys
            conc_L[elem] = CL
            conc_R[elem] = CR

        # Output requested element conc
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                elem = normalize_element_symbol(q.element)
                if output_phase == "extracted_melt":
                    series_map[q] = conc_L.get(elem, np.full_like(F, np.nan))
                elif output_phase == "cumulate":
                    series_map[q] = conc_R.get(elem, np.full_like(F, np.nan))
                else:
                    series_map[q] = conc_melt.get(elem, np.full_like(F, np.nan))

        # Isotopes
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            IC_melt = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC_melt"), np.nan)
            Delta = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "Delta"), 0.0)
            IC_crystal = IC_melt + Delta

            carrier = q.carrier
            if not carrier:
                warnings.append(f"Mush: isotope {q.symbol} missing carrier element; returning NaN")
                series_map[q] = np.full_like(F, np.nan)
                continue

            elem = normalize_element_symbol(carrier)
            Cmelt = conc_melt.get(elem)
            Ccrys = conc_crystal.get(elem)
            CL = conc_L.get(elem)
            CR = conc_R.get(elem)

            if Cmelt is None or Ccrys is None or CL is None or CR is None:
                warnings.append(f"Mush: missing concentration series for isotope carrier element {elem}")
                series_map[q] = np.full_like(F, np.nan)
                continue

            with np.errstate(divide="ignore", invalid="ignore"):
                IC_L = (IC_melt * Cmelt * (1.0 - f_c_eff) + IC_crystal * Ccrys * f_c_eff) / CL
                IC_R = (IC_crystal * Ccrys * (1.0 - f_m) + IC_melt * Cmelt * f_m) / CR

            if output_phase == "extracted_melt":
                series_map[q] = IC_L
            elif output_phase == "cumulate":
                series_map[q] = IC_R
            else:
                series_map[q] = np.full_like(F, IC_melt)

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
