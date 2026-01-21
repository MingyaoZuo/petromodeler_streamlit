"""Streamlit widget: expression builder.

This is a recursive UI that constructs an Expression AST.

Design notes
------------
- Streamlit reruns the script, so we keep widget selections stable via keys
  derived from the provided prefix.
- We keep this widget domain-driven: it returns a domain `Expression`.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from ...application.services.normalization_service import NormalizationService
from ...domain.expressions import BinaryOp, Expression, Leaf
from ...domain.quantities import (
    Anomaly,
    ElementConc,
    IsotopeValue,
    NormalizationRef,
    anomaly_required_elements,
    normalize_element_symbol,
)


def render_expression_builder(
    prefix: str,
    initial: Optional[Expression],
    normalization: NormalizationService,
    depth: int = 0,
    max_depth: int = 3,
) -> Expression:
    """Render UI for an Expression and return the constructed Expression."""

    # Determine default node type from initial
    default_node = "Quantity"
    if isinstance(initial, BinaryOp):
        default_node = "BinaryOp"

    node_type = st.selectbox(
        "节点类型",
        options=["Quantity", "BinaryOp"],
        index=0 if default_node == "Quantity" else 1,
        key=f"{prefix}_node_type",
        disabled=(depth >= max_depth),
    )

    if node_type == "BinaryOp" and depth < max_depth:
        op = st.selectbox(
            "运算符",
            options=["+", "-", "*", "/"],
            index=0,
            key=f"{prefix}_op",
        )
        st.markdown("**左侧**")
        left = render_expression_builder(
            prefix=f"{prefix}_L",
            initial=initial.left if isinstance(initial, BinaryOp) else None,
            normalization=normalization,
            depth=depth + 1,
            max_depth=max_depth,
        )
        st.markdown("**右侧**")
        right = render_expression_builder(
            prefix=f"{prefix}_R",
            initial=initial.right if isinstance(initial, BinaryOp) else None,
            normalization=normalization,
            depth=depth + 1,
            max_depth=max_depth,
        )
        return BinaryOp(op=op, left=left, right=right)

    # Leaf quantity
    default_qty_type = "元素浓度"
    if isinstance(initial, Leaf):
        q = initial.quantity
        if isinstance(q, ElementConc):
            default_qty_type = "元素浓度"
        elif isinstance(q, IsotopeValue):
            default_qty_type = "同位素"
        elif isinstance(q, Anomaly):
            default_qty_type = "Eu异常" if q.kind == "Eu" else "Ce异常"

    qty_type = st.selectbox(
        "Quantity类型",
        options=["元素浓度", "同位素", "Eu异常", "Ce异常"],
        index=["元素浓度", "同位素", "Eu异常", "Ce异常"].index(default_qty_type),
        key=f"{prefix}_qty_type",
    )

    if qty_type == "元素浓度":
        elem = st.text_input("元素符号", value="Sr", key=f"{prefix}_elem")
        elem = normalize_element_symbol(elem)
        return Leaf(ElementConc(element=elem))

    if qty_type == "同位素":
        kind = st.selectbox(
            "同位素类型",
            options=["ratio", "delta", "epsilon"],
            index=0,
            key=f"{prefix}_iso_kind",
        )
        symbol = st.text_input(
            "符号（如 87Sr/86Sr, δ11B, εNd）",
            value="87Sr/86Sr" if kind == "ratio" else ("δ11B" if kind == "delta" else "εNd"),
            key=f"{prefix}_iso_symbol",
        )
        carrier = st.text_input(
            "载体元素（用于质量平衡，例如 87Sr/86Sr 的载体元素=Sr）",
            value="Sr",
            key=f"{prefix}_iso_carrier",
        ).strip()
        carrier = normalize_element_symbol(carrier) if carrier else None
        return Leaf(IsotopeValue(symbol=symbol, kind=kind, carrier=carrier))

    # Anomaly
    anom_kind = "Eu" if qty_type == "Eu异常" else "Ce"
    source = st.selectbox(
        "标准化来源",
        options=normalization.available_sources(),
        index=0,
        key=f"{prefix}_anom_source",
        help="内置表为示例值；可使用 custom 自定义",
    )

    required = anomaly_required_elements(anom_kind)
    base_table = normalization.load(source) if source != "custom" else {}

    values = {}
    if source == "custom":
        st.caption("请输入标准化值（仅需异常计算所需元素）")
        for e in required:
            values[e] = float(st.number_input(f"{e} 标准化值", value=1.0, step=0.1, key=f"{prefix}_norm_{e}"))
    else:
        # show values and still allow overriding via small expander
        st.markdown("标准化值：")
        cols = st.columns(len(required))
        for col, e in zip(cols, required):
            col.metric(e, f"{base_table.get(e, 'NA')}")
        values = {e: float(base_table[e]) for e in required if e in base_table}
        with st.expander("覆盖内置标准化值（可选）", expanded=False):
            for e in required:
                values[e] = float(
                    st.number_input(
                        f"{e}",
                        value=float(values.get(e, 1.0)),
                        step=0.1,
                        key=f"{prefix}_norm_override_{e}",
                    )
                )

    norm = NormalizationRef(source=source, values=values)
    return Leaf(Anomaly(kind=anom_kind, normalization=norm))
