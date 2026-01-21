"""Axis configuration page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ...application.state.axis_state import AxisState
from ..widgets.expression_builder import render_expression_builder


def _inject_axis_layout_style() -> None:
    st.markdown(
        """
        <style>
        section.main > div.block-container {
            max-width: 1180px;
            padding-left: 1.5rem;
            padding-right: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render(controller: AppController) -> None:
    _inject_axis_layout_style()

    st.header("轴配置")
    st.write("在这里配置用于绘图的 X 轴和 Y 轴表达式。表达式支持元素浓度、同位素、Eu 异常和 Ce 异常，并可按顺序链式组合。")

    axis = controller.state.axis
    normalization_sources = controller.available_normalization_sources()

    axis_cols = st.columns(2)

    with axis_cols[0]:
        st.subheader("X 轴")
        x_expr = render_expression_builder(
            prefix="xexpr",
            initial=axis.x_expr,
            normalization_sources=normalization_sources,
            load_normalization_values=controller.load_normalization_values,
            default_element="B",
        )
        st.caption(f"预览：{x_expr.label()}")

    with axis_cols[1]:
        st.subheader("Y 轴")
        y_expr = render_expression_builder(
            prefix="yexpr",
            initial=axis.y_expr,
            normalization_sources=normalization_sources,
            load_normalization_values=controller.load_normalization_values,
            default_element="Sr",
        )
        st.caption(f"预览：{y_expr.label()}")

    new_axis = AxisState(x_expr=x_expr, y_expr=y_expr)
    changed = new_axis != axis

    action_cols = st.columns([1, 4], vertical_alignment="center")
    with action_cols[0]:
        if st.button("保存并应用", type="primary", disabled=not changed, key="apply_axis_btn"):
            controller.set_axis(new_axis)
            st.success("轴配置已应用。")
            st.rerun()
    with action_cols[1]:
        if changed:
            st.warning("轴配置已修改但尚未应用；点击“保存并应用”后才会影响参数组与绘图。")
        else:
            st.caption("轴配置已是最新状态。")
