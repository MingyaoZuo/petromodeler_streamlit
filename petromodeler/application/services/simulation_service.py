"""Simulation service.

Responsibilities:
- validate/fill defaults
- build control grid
- call domain model.simulate
- evaluate x/y expressions
- build a pandas DataFrame detail table for export / inspection
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

import numpy as np
import pandas as pd

from ...domain.common.errors import DomainError, ExpressionError, ModelComputationError, ParameterValidationError
from ...domain.common.types import ControlGrid, ControlVarType, linspace_grid
from ...domain.expressions import Expression
from ...domain.models.base import IModel
from ...domain.parameters.validators import validate_params
from ...domain.quantities import Quantity, format_quantity_label
from ...domain.results import SimulationResult

from ..state.group_state import GroupState
from ..state.axis_state import AxisState
from .parameter_resolver import resolve_requested_quantities, resolve_schema, ensure_defaults


@dataclass
class ValidationReport:
    errors: List[ParameterValidationError]

    def ok(self) -> bool:
        return len(self.errors) == 0


class SimulationService:
    def __init__(self, model_registry) -> None:
        self._registry = model_registry

    def validate_group(self, group: GroupState, axis: AxisState) -> Tuple[ValidationReport, Optional[IModel], Optional[Any]]:
        model = self._registry.get(group.model_id)
        schema = resolve_schema(model, group.group_id, axis.x_expr, axis.y_expr)
        values = ensure_defaults(schema, group.params)
        errs = validate_params(schema.specs, values)
        return ValidationReport(errors=errs), model, schema

    def build_grid(self, model: IModel, group: GroupState) -> ControlGrid:
        spec = model.spec()
        gid = group.group_id
        mid = spec.id

        def g(name: str) -> str:
            # ParamKey string is used directly; pattern matches required_schema definitions
            # We search for the key ending with |mid|global||name
            for k in group.params.keys():
                if k.endswith(f"|{mid}|global||{name}"):
                    return k
            # if not found, reconstruct (most models follow this pattern)
            return f"{gid}|{mid}|global||{name}"

        if spec.control_var == ControlVarType.F:
            F_min = float(group.params.get(g("F_min"), 0.05))
            F_max = float(group.params.get(g("F_max"), 1.0))
            n = int(group.params.get(g("n_points"), 50))
            desc = bool(group.params.get(g("descending"), True))
            arr = linspace_grid(F_min, F_max, n, descending=desc)
            # avoid zeros that can break many formulas
            arr[arr == 0.0] = 1e-12
            return ControlGrid(var=ControlVarType.F, values=arr)

        if spec.control_var == ControlVarType.X:
            X_min = float(group.params.get(g("X_min"), 0.0))
            X_max = float(group.params.get(g("X_max"), 1.0))
            n = int(group.params.get(g("n_points"), 50))
            arr = linspace_grid(X_min, X_max, n, descending=False)
            return ControlGrid(var=ControlVarType.X, values=arr)

        if spec.control_var == ControlVarType.N:
            N_min = float(group.params.get(g("N_min"), 0.0))
            N_max = float(group.params.get(g("N_max"), 3.0))
            n = int(group.params.get(g("n_points"), 50))
            arr = linspace_grid(N_min, N_max, n, descending=False)
            return ControlGrid(var=ControlVarType.N, values=arr)

        raise ValueError(f"Unsupported control var: {spec.control_var}")

    def run_group(self, group: GroupState, axis: AxisState) -> SimulationResult:
        model = self._registry.get(group.model_id)
        schema = resolve_schema(model, group.group_id, axis.x_expr, axis.y_expr)
        values = ensure_defaults(schema, group.params)

        # validate
        errs = validate_params(schema.specs, values)
        if errs:
            raise ModelComputationError("Parameter validation failed")

        grid = self.build_grid(model, group)

        requested = resolve_requested_quantities(axis.x_expr, axis.y_expr)
        result = model.simulate(requested_quantities=requested, params=values, grid=grid)

        # Evaluate x/y
        x = axis.x_expr.evaluate(result.series_map)
        y = axis.y_expr.evaluate(result.series_map)

        # Build detail table
        data = {
            grid.var.value: grid.values,
            axis.x_expr.label(): x,
            axis.y_expr.label(): y,
        }

        # add base quantities as extra columns
        for q in sorted(requested, key=lambda q: format_quantity_label(q)):
            if q in result.series_map:
                data[format_quantity_label(q)] = result.series_map[q]

        df = pd.DataFrame(data)
        result.detail_table = df
        result.metadata["x_label"] = axis.x_expr.label()
        result.metadata["y_label"] = axis.y_expr.label()
        result.metadata["model_id"] = group.model_id
        result.metadata["group_id"] = group.group_id
        return result

    def run_all(self, groups: List[GroupState], axis: AxisState) -> Dict[str, SimulationResult]:
        out: Dict[str, SimulationResult] = {}
        for g in groups:
            if not g.visible:
                continue
            out[g.group_id] = self.run_group(g, axis)
        return out
