"""Streamlit widget: chain-style expression builder."""

from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence

import streamlit as st

from ...domain.expressions import Expression
from ...domain.quantities import (
    Anomaly,
    ElementConc,
    IsotopeValue,
    NormalizationRef,
    anomaly_required_elements,
    normalize_element_symbol,
)
from ..viewmodels.expression_chain import (
    MAX_CHAIN_LENGTH,
    OP_OPTIONS,
    SUPPORTED_ELEMENT_SYMBOLS,
    TYPE_OPTIONS,
    ExpressionRowDraft as _RowDraft,
    chain_rows_to_expression,
    default_element_for_prefix as _default_element_for_prefix,
    default_quantity as _default_quantity,
    expression_to_chain_rows,
    infer_carrier_from_symbol as _infer_carrier_from_symbol,
)


def _element_select(prefix: str, row_index: int, current_element: str, default_element: str) -> ElementConc:
    options = list(SUPPORTED_ELEMENT_SYMBOLS)
    custom_label = "自定义"
    normalized_current = normalize_element_symbol(current_element)
    selected = normalized_current if normalized_current in options else custom_label

    choice = st.selectbox(
        "元素符号",
        options=options + [custom_label],
        index=(options + [custom_label]).index(selected),
        key=f"{prefix}_row{row_index}_element_choice",
    )

    if choice != custom_label:
        return ElementConc(element=choice)

    custom_value = st.text_input(
        "自定义元素符号",
        value=normalized_current if normalized_current not in ("", custom_label) else default_element,
        key=f"{prefix}_row{row_index}_element_custom",
        placeholder="如 Sr、Nd、U",
    )
    normalized = normalize_element_symbol(custom_value)
    return ElementConc(element=normalized or default_element)


def _render_isotope(prefix: str, row_index: int, quantity: IsotopeValue) -> IsotopeValue:
    preset_map = {
        "H": ("delta", "δ2H", "H"),
        "Li": ("delta", "δ7Li", "Li"),
        "B": ("delta", "δ11B", "B"),
        "C": ("delta", "δ13C", "C"),
        "O": ("delta", "δ18O", "O"),
        "Mg": ("delta", "δ26Mg", "Mg"),
        "S": ("delta", "δ34S", "S"),
        "87Sr/86Sr": ("ratio", "87Sr/86Sr", "Sr"),
        "εNd": ("epsilon", "εNd", "Nd"),
    }

    current_symbol = (quantity.symbol or "").strip()
    custom_label = "自定义"
    default_preset = custom_label
    for preset_name, (_, preset_symbol, _) in preset_map.items():
        if preset_symbol == current_symbol:
            default_preset = preset_name
            break
    if current_symbol.startswith("ε") and current_symbol not in preset_map:
        default_preset = custom_label

    preset_options = list(preset_map.keys()) + [custom_label]
    preset = st.selectbox(
        "同位素符号",
        options=preset_options,
        index=preset_options.index(default_preset),
        key=f"{prefix}_row{row_index}_isotope_preset",
    )

    if preset != custom_label:
        kind, symbol, carrier = preset_map[preset]
        return IsotopeValue(symbol=symbol, kind=kind, carrier=carrier)

    kind_options = ["delta", "ratio", "epsilon"]
    current_kind = quantity.kind if quantity.kind in kind_options else "delta"
    kind = st.selectbox(
        "自定义类型",
        options=kind_options,
        index=kind_options.index(current_kind),
        key=f"{prefix}_row{row_index}_isotope_kind",
    )
    default_symbol = "δ11B" if kind == "delta" else "87Sr/86Sr" if kind == "ratio" else "εNd"
    symbol = (
        st.text_input(
            "符号",
            value=current_symbol or default_symbol,
            key=f"{prefix}_row{row_index}_isotope_symbol",
            placeholder="如 δ11B、87Sr/86Sr、εNd",
        )
        .strip()
        or default_symbol
    )
    carrier = _infer_carrier_from_symbol(symbol)
    if carrier is None:
        st.caption("未识别载体元素")
    return IsotopeValue(symbol=symbol, kind=kind, carrier=carrier)


def _render_anomaly(
    prefix: str,
    row_index: int,
    quantity: Anomaly,
    normalization_sources: Sequence[str],
    load_normalization_values: Callable[[str], Mapping[str, float]],
) -> Anomaly:
    required = anomaly_required_elements(quantity.kind)
    available_sources = list(normalization_sources)
    current_source = quantity.normalization.source if quantity.normalization else "chondrite"
    source = st.selectbox(
        "标准化来源",
        options=available_sources,
        index=available_sources.index(current_source) if current_source in available_sources else 0,
        key=f"{prefix}_row{row_index}_anom_source",
    )

    base_values = load_normalization_values(source) if source != "custom" else {}
    values: dict[str, float] = {}

    if source == "custom":
        for element in required:
            values[element] = float(
                st.number_input(
                    f"{element} 标准化值",
                    value=float(quantity.normalization.values.get(element, 1.0) if quantity.normalization.values else 1.0),
                    step=0.1,
                    key=f"{prefix}_row{row_index}_anom_custom_{element}",
                )
            )
    else:
        cols = st.columns(len(required))
        for col, element in zip(cols, required):
            col.metric(element, f"{base_values.get(element, 'NA')}")
        values = {element: float(base_values[element]) for element in required if element in base_values}
        with st.expander("覆盖内置标准化值", expanded=False):
            for element in required:
                values[element] = float(
                    st.number_input(
                        f"{element}",
                        value=float(values.get(element, 1.0)),
                        step=0.1,
                        key=f"{prefix}_row{row_index}_anom_override_{element}",
                    )
                )

    return Anomaly(kind=quantity.kind, normalization=NormalizationRef(source=source, values=values))


def _render_row(
    prefix: str,
    row_index: int,
    row: _RowDraft,
    normalization_sources: Sequence[str],
    load_normalization_values: Callable[[str], Mapping[str, float]],
    default_element: str,
) -> _RowDraft:
    with st.container(border=True):
        top_cols = st.columns([0.95, 3.05], vertical_alignment="top")
        with top_cols[0]:
            quantity_type = st.selectbox(
                "类型",
                options=TYPE_OPTIONS,
                index=TYPE_OPTIONS.index(row.quantity_type) if row.quantity_type in TYPE_OPTIONS else 0,
                key=f"{prefix}_row{row_index}_type",
            )
        with top_cols[1]:
            quantity = row.quantity
            if quantity_type == "元素浓度":
                current_element = quantity.element if isinstance(quantity, ElementConc) else default_element
                quantity = _element_select(prefix, row_index, current_element, default_element)
            elif quantity_type == "同位素":
                quantity = _render_isotope(
                    prefix,
                    row_index,
                    quantity if isinstance(quantity, IsotopeValue) else _default_quantity("同位素", default_element),
                )
            elif quantity_type in {"Eu异常", "Ce异常"}:
                default_kind = "Eu" if quantity_type == "Eu异常" else "Ce"
                default_anomaly = (
                    quantity
                    if isinstance(quantity, Anomaly) and quantity.kind == default_kind
                    else _default_quantity(quantity_type, default_element)
                )
                quantity = _render_anomaly(
                    prefix,
                    row_index,
                    default_anomaly,
                    normalization_sources,
                    load_normalization_values,
                )
            else:
                quantity = _default_quantity("元素浓度", default_element)
                _element_select(prefix, row_index, default_element, default_element)

        bottom_cols = st.columns([0.95, 0.75, 3.05], vertical_alignment="top")
        with bottom_cols[1]:
            op = st.selectbox(
                "运算符",
                options=OP_OPTIONS,
                index=OP_OPTIONS.index(row.op_to_next) if row.op_to_next in OP_OPTIONS else 0,
                key=f"{prefix}_row{row_index}_op",
            )

    return _RowDraft(quantity_type=quantity_type, quantity=quantity, op_to_next=op)


def render_expression_builder(
    prefix: str,
    initial: Optional[Expression],
    normalization_sources: Sequence[str],
    load_normalization_values: Callable[[str], Mapping[str, float]],
    depth: int = 0,
    max_depth: int = 3,
    default_element: Optional[str] = None,
) -> Expression:
    """Render a chain-style UI for an Expression and return the built tree."""

    del depth, max_depth

    axis_default_element = default_element or _default_element_for_prefix(prefix)
    rows = expression_to_chain_rows(initial, axis_default_element)
    rendered_rows: list[_RowDraft] = []

    row_index = 0
    while row_index < MAX_CHAIN_LENGTH:
        if row_index >= len(rows):
            rows.append(_RowDraft(quantity_type="元素浓度", quantity=_default_quantity("元素浓度", axis_default_element)))

        row = _render_row(
            prefix,
            row_index,
            rows[row_index],
            normalization_sources,
            load_normalization_values,
            axis_default_element,
        )
        rendered_rows.append(row)

        if row.op_to_next == "无" or row_index == MAX_CHAIN_LENGTH - 1:
            break

        row_index += 1

    if not rendered_rows:
        rendered_rows = [_RowDraft(quantity_type="元素浓度", quantity=_default_quantity("元素浓度", axis_default_element))]

    return chain_rows_to_expression(rendered_rows, axis_default_element)
