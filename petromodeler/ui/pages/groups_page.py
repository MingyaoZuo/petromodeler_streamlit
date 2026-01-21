"""Parameter groups page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ..session_keys import ACTIVE_GROUP_ID, GROUP_ADDED
from .group_creation_panel import render as render_group_creation_panel
from .group_editor_panel import render as render_group_editor
from .plot_page import render as render_plot


def render(controller: AppController) -> None:
    rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    active_group_id = st.session_state.get(ACTIVE_GROUP_ID)

    st.header("参数组管理")
    st.write("每个参数组独立选择模型与参数，可同时绘制多组结果。")

    left, right = st.columns([3, 2])
    with left:
        render_group_creation_panel(controller)
        if st.session_state.pop(GROUP_ADDED, False):
            st.success("已添加参数组")

        if not controller.state.groups:
            st.info("暂无参数组，请先添加。")
        else:
            model_labels = controller.model_labels()
            group_count = len(controller.state.groups)
            for group_index, group in enumerate(controller.state.groups):
                render_group_editor(
                    controller=controller,
                    group_id=group.group_id,
                    model_labels=model_labels,
                    active_group_id=active_group_id,
                    group_index=group_index,
                    group_count=group_count,
                    rerun=rerun,
                )

    with right:
        st.subheader("建模结果显示")
        render_plot(controller, show_header=False)
