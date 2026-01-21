"""MM model (Magma mixing / 岩浆混合).

Formulas (provided summary):
- Element concentration:
    C_mix = C_A * X + C_B * (1 - X)
- Isotope value (ratio):
    IC_mix = IC_A * (C_A*X / C_mix) + IC_B * (C_B*(1-X) / C_mix)

For stable isotope delta, we use the same concentration-weighted mixing in delta
as a practical approximation.

Control variable: X in [0,1] (fraction of endmember A)
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


class MMModel(IModel):
    MODEL_ID = "mm"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="MM (岩浆混合)", control_var=ControlVarType.X)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        specs: List[ParameterSpec] = []

        specs.extend(control_grid_specs(group_id, self.MODEL_ID, ControlVarType.X))

        # Determine which elements we need endmember concentrations for:
        # - all ElementConc quantities
        # - carrier element of any isotope quantity
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
                    key=ParamKey(group_id, self.MODEL_ID, "endmember_A", qid, "C"),
                    label=f"端元A {elem} 浓度 C_A",
                    kind="float",
                    default=100.0,
                    min_value=0.0,
                    step=10.0,
                    group="Endmembers",
                )
            )
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "endmember_B", qid, "C"),
                    label=f"端元B {elem} 浓度 C_B",
                    kind="float",
                    default=50.0,
                    min_value=0.0,
                    step=10.0,
                    group="Endmembers",
                )
            )

        # Isotope values for each isotope quantity
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue
            qid = quantity_id(q)
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "endmember_A", qid, "IC"),
                    label=f"端元A {q.symbol}",
                    kind="float",
                    default=0.703 if q.kind == "ratio" else 0.0,
                    step=0.1,
                    group="Endmembers",
                )
            )
            specs.append(
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "endmember_B", qid, "IC"),
                    label=f"端元B {q.symbol}",
                    kind="float",
                    default=0.710 if q.kind == "ratio" else 0.0,
                    step=0.1,
                    group="Endmembers",
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
        if grid.var != ControlVarType.X:
            raise ValueError("MMModel requires ControlGrid var=X")

        X = np.asarray(grid.values, dtype=float)

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        # Precompute mixed concentrations for all needed elements
        conc_series_by_elem: Dict[str, np.ndarray] = {}

        def get_CA_CB(elem: str) -> tuple[float, float]:
            qid = f"conc:melt:{elem}"
            CA = get_float(params, make_key(group_id, self.MODEL_ID, "endmember_A", qid, "C"), np.nan)
            CB = get_float(params, make_key(group_id, self.MODEL_ID, "endmember_B", qid, "C"), np.nan)
            return CA, CB

        # build list of needed elements similarly to schema
        elements_needed: Set[str] = set()
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                elements_needed.add(normalize_element_symbol(q.element))
            elif isinstance(q, IsotopeValue) and q.carrier:
                elements_needed.add(normalize_element_symbol(q.carrier))

        for elem in elements_needed:
            CA, CB = get_CA_CB(elem)
            conc_series_by_elem[elem] = CA * X + CB * (1.0 - X)

        # Fill ElementConc series
        for q in requested_quantities:
            if isinstance(q, ElementConc):
                elem = normalize_element_symbol(q.element)
                series_map[q] = conc_series_by_elem.get(elem, np.full_like(X, np.nan))

        # Fill isotope series
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue

            qid = quantity_id(q)
            ICA = get_float(params, make_key(group_id, self.MODEL_ID, "endmember_A", qid, "IC"), np.nan)
            ICB = get_float(params, make_key(group_id, self.MODEL_ID, "endmember_B", qid, "IC"), np.nan)

            carrier = q.carrier
            if not carrier:
                warnings.append(f"MM: isotope {q.symbol} missing carrier element; returning NaN")
                series_map[q] = np.full_like(X, np.nan)
                continue

            elem = normalize_element_symbol(carrier)
            CA, CB = get_CA_CB(elem)
            Cmix = conc_series_by_elem.get(elem)
            if Cmix is None:
                warnings.append(f"MM: missing carrier concentration for {q.symbol} (carrier={elem}); returning NaN")
                series_map[q] = np.full_like(X, np.nan)
                continue

            # Avoid divide-by-zero
            with np.errstate(divide="ignore", invalid="ignore"):
                wA = (CA * X) / Cmix
                wB = (CB * (1.0 - X)) / Cmix
                out = ICA * wA + ICB * wB

            series_map[q] = out

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
