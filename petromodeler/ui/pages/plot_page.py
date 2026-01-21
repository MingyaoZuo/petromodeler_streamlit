"""Plot page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController


def render(controller: AppController, show_header: bool = True) -> None:
    if show_header:
        st.header("建模结果显示")

    # plot settings
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        controller.state.plot.title = st.text_input("图标题", value=controller.state.plot.title, key="plot_title")
    with col2:
        controller.state.plot.show_dataset = st.checkbox("显示用户数据", value=controller.state.plot.show_dataset, key="show_dataset")
    with col3:
        controller.state.plot.show_legend = st.checkbox("显示图例", value=controller.state.plot.show_legend, key="show_legend")

    if st.button("计算并绘图", key="run_all_plot"):
        results = controller.run_all()
        st.session_state._latest_results = results

    results = st.session_state.get("_latest_results", {})
    if results:
        fig = controller.build_plot(results)
        st.pyplot(fig, use_container_width=True)

        # group messages
        for g in controller.state.groups:
            if not g.visible:
                continue
            if g.last_error:
                st.error(f"{g.name}: {g.last_error}")
            elif g.last_result and getattr(g.last_result, "warnings", None):
                for w in g.last_result.warnings:
                    st.warning(f"{g.name}: {w}")

        st.subheader("查看计算详情")
        for g in controller.state.groups:
            if not g.visible or not g.last_result or g.last_result.detail_table is None:
                continue
            with st.expander(f"{g.name} 计算详情", expanded=False):
                df = g.last_result.detail_table
                st.dataframe(df, use_container_width=True)
                # download
                excel_bytes = controller.exporter.dataframe_to_excel_bytes(df)
                st.download_button(
                    label="下载Excel",
                    data=excel_bytes,
                    file_name=f"{g.name}_details.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{g.group_id}",
                )
    else:
        st.info("点击 '计算并绘图' 以生成结果。")
