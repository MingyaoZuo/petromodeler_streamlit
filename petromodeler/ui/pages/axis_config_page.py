"""Axis configuration page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ...application.state.axis_state import AxisState
from ..widgets.expression_builder import render_expression_builder


def render(controller: AppController) -> None:
    st.header("x / y 轴体系配置")
    st.write("在这里配置用于绘图的 X 与 Y 轴表达式。表达式可以是单一 Quantity，也可以是两个 Quantity 的四则运算组合。")

    axis = controller.state.axis
    norm = controller.norm

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("X 轴")
        x_expr = render_expression_builder(prefix="xexpr", initial=axis.x_expr, normalization=norm)
        st.caption(f"预览: {x_expr.label()}")
    with col2:
        st.subheader("Y 轴")
        y_expr = render_expression_builder(prefix="yexpr", initial=axis.y_expr, normalization=norm)
        st.caption(f"预览: {y_expr.label()}")

    new_axis = AxisState(x_expr=x_expr, y_expr=y_expr)
    if new_axis != axis:
        controller.set_axis(new_axis)
        st.session_state.pop("_latest_results", None)
        st.caption("轴配置已自动应用（无需点击保存）。")
