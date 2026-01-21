"""Axis expressions.

An Expression is an AST that combines Quantities via arithmetic operations.

Key responsibilities:
- determine which base quantities are needed to evaluate x/y
- evaluate x/y arrays from a map {Quantity -> array}
- format axis labels
- serialize/deserialize to support project save/load
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Set, Tuple, Union

import numpy as np

from .common.errors import ExpressionError
from .common.types import NumericArray
from .quantities import (
    Anomaly,
    ElementConc,
    IsotopeValue,
    NormalizationRef,
    Quantity,
    anomaly_required_elements,
    expand_base_quantities,
    format_quantity_label,
    quantity_id,
)


BinaryOpSymbol = Literal["+", "-", "*", "/"]


class Expression:
    """Base class for expressions."""

    def dependencies(self) -> Set[Quantity]:
        """Return all base quantities needed to evaluate this expression."""

        raise NotImplementedError

    def evaluate(self, series_map: Mapping[Quantity, NumericArray]) -> NumericArray:
        raise NotImplementedError

    def label(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Leaf(Expression):
    quantity: Quantity

    def dependencies(self) -> Set[Quantity]:
        # Expand anomalies into their required element concentrations
        deps: Set[Quantity] = set()
        for q in expand_base_quantities(self.quantity):
            deps.add(q)
        return deps

    def evaluate(self, series_map: Mapping[Quantity, NumericArray]) -> NumericArray:
        q = self.quantity
        if isinstance(q, (ElementConc, IsotopeValue)):
            try:
                return np.asarray(series_map[q], dtype=float)
            except KeyError as e:
                raise ExpressionError(f"Missing series for quantity: {format_quantity_label(q)}") from e

        if isinstance(q, Anomaly):
            # Compute Eu/Eu* or Ce/Ce* using normalized concentrations
            required_elems = anomaly_required_elements(q.kind)
            # build element conc objects with same context
            conc_qs = [ElementConc(e, context=q.context) for e in required_elems]
            for cq in conc_qs:
                if cq not in series_map:
                    raise ExpressionError(f"Missing concentration series for anomaly element: {format_quantity_label(cq)}")

            norm_values = q.normalization.values or {}
            # For built-in normalization sources, the application layer should populate values.
            # If still missing, error with a helpful message.
            missing = [e for e in required_elems if e not in norm_values]
            if missing:
                raise ExpressionError(
                    f"Normalization values missing for {q.normalization.source}: {', '.join(missing)}"
                )

            series_norm = []
            for elem, cq in zip(required_elems, conc_qs):
                series_norm.append(np.asarray(series_map[cq], dtype=float) / float(norm_values[elem]))

            # geometric mean for *
            if q.kind == "Eu":
                eu_n, sm_n, gd_n = series_norm
                eu_star = np.sqrt(sm_n * gd_n)
                return eu_n / eu_star
            ce_n, la_n, pr_n = series_norm
            ce_star = np.sqrt(la_n * pr_n)
            return ce_n / ce_star

        raise ExpressionError(f"Unsupported leaf quantity type: {type(q)}")

    def label(self) -> str:
        return format_quantity_label(self.quantity)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "leaf", "quantity": _quantity_to_dict(self.quantity)}


@dataclass(frozen=True)
class BinaryOp(Expression):
    op: BinaryOpSymbol
    left: Expression
    right: Expression

    def dependencies(self) -> Set[Quantity]:
        return set(self.left.dependencies()) | set(self.right.dependencies())

    def evaluate(self, series_map: Mapping[Quantity, NumericArray]) -> NumericArray:
        a = self.left.evaluate(series_map)
        b = self.right.evaluate(series_map)
        if self.op == "+":
            return a + b
        if self.op == "-":
            return a - b
        if self.op == "*":
            return a * b
        if self.op == "/":
            # avoid dividing by zero silently
            with np.errstate(divide="raise", invalid="raise"):
                try:
                    return a / b
                except FloatingPointError as e:
                    raise ExpressionError("Division by zero or invalid operation in expression") from e
        raise ExpressionError(f"Unsupported operator: {self.op}")

    def label(self) -> str:
        return f"({self.left.label()} {self.op} {self.right.label()})"

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "binop", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict()}


def expression_from_dict(data: Dict[str, Any]) -> Expression:
    t = data.get("type")
    if t == "leaf":
        return Leaf(quantity=_quantity_from_dict(data["quantity"]))
    if t == "binop":
        return BinaryOp(
            op=data["op"],
            left=expression_from_dict(data["left"]),
            right=expression_from_dict(data["right"]),
        )
    raise ExpressionError(f"Unknown expression type: {t}")


def _quantity_to_dict(q: Quantity) -> Dict[str, Any]:
    if isinstance(q, ElementConc):
        return {"type": "conc", "element": q.element, "context": q.context}
    if isinstance(q, IsotopeValue):
        return {
            "type": "iso",
            "symbol": q.symbol,
            "kind": q.kind,
            "carrier": q.carrier,
            "context": q.context,
        }
    if isinstance(q, Anomaly):
        return {
            "type": "anom",
            "kind": q.kind,
            "context": q.context,
            "normalization": {
                "source": q.normalization.source,
                "values": dict(q.normalization.values) if q.normalization.values else None,
            },
        }
    raise ExpressionError(f"Unsupported quantity type: {type(q)}")


def _quantity_from_dict(data: Dict[str, Any]) -> Quantity:
    t = data.get("type")
    if t == "conc":
        return ElementConc(element=data["element"], context=data.get("context", "melt"))
    if t == "iso":
        return IsotopeValue(
            symbol=data["symbol"],
            kind=data["kind"],
            carrier=data.get("carrier"),
            context=data.get("context", "melt"),
        )
    if t == "anom":
        norm = data.get("normalization", {})
        return Anomaly(
            kind=data["kind"],
            context=data.get("context", "melt"),
            normalization=NormalizationRef(source=norm.get("source", "chondrite"), values=norm.get("values")),
        )
    raise ExpressionError(f"Unknown quantity dict type: {t}")
