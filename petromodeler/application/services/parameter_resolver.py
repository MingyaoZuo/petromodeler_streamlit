"""Parameter schema resolver.

Given axis expressions and a model, determine which base quantities are required,
then ask the model to produce a UISchema.

This module is the main bridge between:
- Axis selections (x/y Expression)
- Model parameter needs
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Set

from ...domain.expressions import Expression
from ...domain.quantities import Quantity
from ...domain.models.base import IModel
from ...domain.parameters.specs import UISchema


def resolve_requested_quantities(x_expr: Expression, y_expr: Expression) -> Set[Quantity]:
    return set(x_expr.dependencies()) | set(y_expr.dependencies())


def resolve_schema(model: IModel, group_id: str, x_expr: Expression, y_expr: Expression) -> UISchema:
    requested = resolve_requested_quantities(x_expr, y_expr)
    return model.required_schema(group_id=group_id, requested_quantities=requested)


def ensure_defaults(schema: UISchema, values: Dict[str, Any]) -> Dict[str, Any]:
    """Fill missing keys with schema defaults."""
    out = dict(values)
    for spec in schema.specs:
        k = spec.key.to_string()
        if k not in out:
            out[k] = spec.default
    return out
