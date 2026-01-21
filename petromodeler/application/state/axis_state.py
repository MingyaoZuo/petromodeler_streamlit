"""Axis configuration state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...domain.expressions import Expression, Leaf
from ...domain.quantities import ElementConc


@dataclass
class AxisState:
    x_expr: Expression
    y_expr: Expression

    def labels(self) -> tuple[str, str]:
        return (self.x_expr.label(), self.y_expr.label())


def default_axis_state() -> AxisState:
    # Default to Sr vs Nd as a simple placeholder
    return AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd")))
