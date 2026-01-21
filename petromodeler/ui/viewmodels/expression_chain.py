"""View model helpers for the chain-style expression builder."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from ...domain.expressions import BinaryOp, Expression, Leaf
from ...domain.quantities import (
    Anomaly,
    ElementConc,
    IsotopeValue,
    NormalizationRef,
    normalize_element_symbol,
)


TYPE_OPTIONS = ["元素浓度", "同位素", "Eu异常", "Ce异常"]
OP_OPTIONS = ["无", "+", "-", "*", "/"]
MAX_CHAIN_LENGTH = 12

SUPPORTED_ELEMENT_SYMBOLS = [
    "B",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Ni",
    "Co",
    "Cu",
    "Zn",
    "Sr",
    "Y",
    "Zr",
    "Nb",
    "Ba",
    "Hf",
    "Ta",
]

DEFAULT_ELEMENT_BY_AXIS = {"x": "B", "y": "Sr"}


@dataclass(frozen=True)
class ExpressionRowDraft:
    quantity_type: str
    quantity: object
    op_to_next: str = "无"


def default_element_for_prefix(prefix: str) -> str:
    prefix_lower = prefix.lower()
    if prefix_lower.startswith("x"):
        return DEFAULT_ELEMENT_BY_AXIS["x"]
    if prefix_lower.startswith("y"):
        return DEFAULT_ELEMENT_BY_AXIS["y"]
    return "Sr"


def default_quantity(quantity_type: str, default_element: str = "Sr"):
    if quantity_type == "同位素":
        return IsotopeValue(symbol="δ11B", kind="delta", carrier="B")
    if quantity_type == "Eu异常":
        return Anomaly(
            kind="Eu",
            normalization=NormalizationRef(source="chondrite", values={"Eu": 1.0, "Sm": 1.0, "Gd": 1.0}),
        )
    if quantity_type == "Ce异常":
        return Anomaly(
            kind="Ce",
            normalization=NormalizationRef(source="chondrite", values={"Ce": 1.0, "La": 1.0, "Pr": 1.0}),
        )
    return ElementConc(element=default_element)


def quantity_type_for(quantity: object) -> str:
    if isinstance(quantity, ElementConc):
        return "元素浓度"
    if isinstance(quantity, IsotopeValue):
        return "同位素"
    if isinstance(quantity, Anomaly):
        return "Eu异常" if quantity.kind == "Eu" else "Ce异常"
    return "元素浓度"


def infer_carrier_from_symbol(symbol: str) -> Optional[str]:
    text = (symbol or "").strip()
    if not text:
        return None

    match = re.match(r"^ε\s*([A-Za-z]{1,2})", text)
    if match:
        return normalize_element_symbol(match.group(1))

    match = re.match(r"^δ\s*\d*\s*([A-Za-z]{1,2})", text)
    if match:
        return normalize_element_symbol(match.group(1))

    if "/" in text:
        left, right = text.split("/", 1)
        left_match = re.search(r"([A-Za-z]{1,2})", left)
        right_match = re.search(r"([A-Za-z]{1,2})", right)
        if left_match and right_match and left_match.group(1) == right_match.group(1):
            return normalize_element_symbol(left_match.group(1))
        if left_match:
            return normalize_element_symbol(left_match.group(1))

    tokens = re.findall(r"([A-Za-z]{1,2})", text)
    return normalize_element_symbol(tokens[-1]) if tokens else None


def _initial_rows(initial: Optional[Expression], default_element: str) -> list[ExpressionRowDraft]:
    if initial is None:
        return [ExpressionRowDraft(quantity_type="元素浓度", quantity=default_quantity("元素浓度", default_element))]

    if isinstance(initial, BinaryOp):
        left_rows = _initial_rows(initial.left, default_element)
        right_rows = _initial_rows(initial.right, default_element)
        left_rows[-1] = ExpressionRowDraft(
            quantity_type=left_rows[-1].quantity_type,
            quantity=left_rows[-1].quantity,
            op_to_next=initial.op,
        )
        return left_rows + right_rows

    return [ExpressionRowDraft(quantity_type=quantity_type_for(initial.quantity), quantity=initial.quantity)]


def expression_to_chain_rows(expression: Optional[Expression], default_element: str = "Sr") -> list[ExpressionRowDraft]:
    """Flatten an expression into left-to-right chain rows."""

    return _initial_rows(expression, default_element)


def _row_to_leaf(row: ExpressionRowDraft, default_element: str) -> Leaf:
    quantity = row.quantity
    if isinstance(quantity, (ElementConc, IsotopeValue, Anomaly)):
        return Leaf(quantity)
    return Leaf(ElementConc(element=default_element))


def chain_rows_to_expression(rows: Sequence[ExpressionRowDraft], default_element: str = "Sr") -> Expression:
    """Convert rendered chain rows back into a domain expression."""

    if not rows:
        return Leaf(ElementConc(element=default_element))

    expr: Expression = _row_to_leaf(rows[0], default_element)
    for index, row in enumerate(rows[:-1]):
        if row.op_to_next == "无":
            break
        expr = BinaryOp(op=row.op_to_next, left=expr, right=_row_to_leaf(rows[index + 1], default_element))
    return expr
