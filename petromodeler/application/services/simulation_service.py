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
from ...domain.parameters.grid import (
    CONTROL_GRID_DEFAULTS,
    GRID_DESCENDING,
    GRID_MODE,
    GRID_N_POINTS,
    GRID_STEP,
    control_grid_key,
    control_grid_value_name,
)
from ...domain.parameters.validators import validate_params
from ...domain.quantities import Quantity, format_quantity_label

from ..results import GroupRunResult
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
        control_var = spec.control_var

        if control_var not in CONTROL_GRID_DEFAULTS:
            raise ValueError(f"Unsupported control var: {control_var}")

        defaults = CONTROL_GRID_DEFAULTS[control_var]

        def param(name: str, default: Any) -> Any:
            return group.params.get(control_grid_key(gid, mid, name), default)

        def make_grid(start: float, stop: float, descending: bool = False) -> np.ndarray:
            mode = str(param(GRID_MODE, "By points"))
            if mode == "By step":
                step = float(param(GRID_STEP, defaults.step))
                if step <= 0:
                    raise ValueError("grid_step must be > 0")
                lo, hi = sorted((float(start), float(stop)))
                count = int(np.floor((hi - lo) / step)) + 1
                arr = lo + step * np.arange(max(count, 1), dtype=float)
                if arr.size == 0 or not np.isclose(arr[-1], hi):
                    arr = np.append(arr, hi)
                if descending:
                    arr = arr[::-1]
                return arr

            n = int(param(GRID_N_POINTS, defaults.n_points))
            return linspace_grid(start, stop, n, descending=descending)

        start = float(param(control_grid_value_name(control_var, "min"), defaults.min_value))
        stop = float(param(control_grid_value_name(control_var, "max"), defaults.max_value))
        descending = (
            bool(param(GRID_DESCENDING, defaults.descending))
            if defaults.include_descending
            else False
        )
        arr = make_grid(start, stop, descending=descending)

        if control_var == ControlVarType.F:
            arr[arr == 0.0] = 1e-12
        return ControlGrid(var=control_var, values=arr)

    def run_group(self, group: GroupState, axis: AxisState) -> GroupRunResult:
        model = self._registry.get(group.model_id)
        schema = resolve_schema(model, group.group_id, axis.x_expr, axis.y_expr)
        values = ensure_defaults(schema, group.params)

        # validate
        errs = validate_params(schema.specs, values)
        if errs:
            raise ModelComputationError("Parameter validation failed")

        grid = self.build_grid(model, group)

        requested = resolve_requested_quantities(axis.x_expr, axis.y_expr)
        result = model.simulate(
            requested_quantities=requested,
            group_id=group.group_id,
            params=values,
            grid=grid,
        )

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
        return GroupRunResult(
            domain_result=result,
            detail_table=df,
            x_label=axis.x_expr.label(),
            y_label=axis.y_expr.label(),
            model_id=group.model_id,
            group_id=group.group_id,
        )

    def run_all(self, groups: List[GroupState], axis: AxisState) -> Dict[str, GroupRunResult]:
        out: Dict[str, GroupRunResult] = {}
        for g in groups:
            if not g.visible:
                continue
            out[g.group_id] = self.run_group(g, axis)
        return out
