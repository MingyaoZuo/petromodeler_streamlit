"""Plot page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...application.controllers.app_controller import AppController
from ...application.state.plot_state import CurveStyle, PointStyle
from ..session_keys import (
    DETAIL_SAVE_MESSAGE,
    DETAIL_SAVE_PATH,
    PLOT_SAVE_MESSAGE,
    PLOT_SAVE_PATH,
)


MARKER_OPTIONS = {
    "无": "",
    "圆圈": "o",
    "方框": "s",
    "三角形": "^",
    "菱形": "D",
    "十字": "X",
    "星形": "*",
}
DATA_MARKER_OPTIONS = {label: value for label, value in MARKER_OPTIONS.items() if value}
LINE_STYLE_OPTIONS = {
    "实线": "-",
    "虚线": "--",
    "点线": ":",
    "点划线": "-.",
    "无线条": "None",
}
DEFAULT_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def _option_index(options: dict[str, str], value: str) -> int:
    values = list(options.values())
    return values.index(value) if value in values else 0


def _render_style_editor(controller: AppController, results: dict) -> None:
    """Render controls for the same items that appear in the plot legend."""
    with st.expander("编辑图例与绘图样式", expanded=False):
        st.caption("设置会同时应用到图例、页面预览和下载的绘图文件。")

        st.markdown("**坐标轴显示**")
        x_axis_column, y_axis_column = st.columns(2)
        with x_axis_column:
            x_axis_log_scale = st.checkbox(
                "横坐标使用对数刻度",
                value=controller.state.plot.x_axis_log_scale,
                key="plot_x_axis_log_scale",
            )
        with y_axis_column:
            y_axis_log_scale = st.checkbox(
                "纵坐标使用对数刻度",
                value=controller.state.plot.y_axis_log_scale,
                key="plot_y_axis_log_scale",
            )
        controller.set_plot_axis_log_scale(x_axis_log_scale, y_axis_log_scale)

        visible_groups = [
            group
            for group in controller.state.groups
            if group.visible and group.group_id in results
        ]
        if visible_groups:
            st.markdown("**参数组曲线**")
        for index, group in enumerate(visible_groups):
            default_color = DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
            style = controller.state.plot.curve_styles_by_group.get(group.group_id)
            style = style or CurveStyle(line_color=default_color)
            with st.container(border=True):
                st.write(group.name)
                first, second, third = st.columns(3)
                with first:
                    line_color = st.color_picker(
                        "曲线颜色",
                        value=style.line_color or default_color,
                        key=f"curve_line_color_{group.group_id}",
                    )
                    line_style = st.selectbox(
                        "线型",
                        list(LINE_STYLE_OPTIONS),
                        index=_option_index(LINE_STYLE_OPTIONS, style.line_style),
                        key=f"curve_line_style_{group.group_id}",
                    )
                with second:
                    line_width = st.number_input(
                        "线宽",
                        min_value=0.1,
                        max_value=10.0,
                        value=float(style.line_width),
                        step=0.1,
                        key=f"curve_line_width_{group.group_id}",
                    )
                    marker = st.selectbox(
                        "曲线标记",
                        list(MARKER_OPTIONS),
                        index=_option_index(MARKER_OPTIONS, style.marker),
                        key=f"curve_marker_{group.group_id}",
                    )
                with third:
                    marker_facecolor = st.color_picker(
                        "标记填充色",
                        value=style.marker_facecolor or line_color,
                        key=f"curve_marker_face_{group.group_id}",
                    )
                    marker_edgecolor = st.color_picker(
                        "标记轮廓色",
                        value=style.marker_edgecolor or line_color,
                        key=f"curve_marker_edge_{group.group_id}",
                    )
                controller.set_group_curve_style(
                    group.group_id,
                    CurveStyle(
                        line_color=line_color,
                        line_style=LINE_STYLE_OPTIONS[line_style],
                        line_width=float(line_width),
                        marker=MARKER_OPTIONS[marker],
                        marker_facecolor=marker_facecolor,
                        marker_edgecolor=marker_edgecolor,
                    ),
                )

        dataset_labels = controller.dataset_plot_labels()
        if dataset_labels:
            st.markdown("**用户数据点**")
        for index, label in enumerate(dataset_labels):
            default_color = DEFAULT_COLORS[(len(visible_groups) + index) % len(DEFAULT_COLORS)]
            style = controller.state.plot.dataset_point_styles_by_label.get(label)
            style = style or PointStyle(facecolor=default_color, edgecolor=default_color)
            with st.container(border=True):
                st.write(label)
                first, second, third = st.columns(3)
                with first:
                    marker = st.selectbox(
                        "数据点形状",
                        list(DATA_MARKER_OPTIONS),
                        index=_option_index(DATA_MARKER_OPTIONS, style.marker),
                        key=f"data_marker_{label}",
                    )
                with second:
                    facecolor = st.color_picker(
                        "填充色",
                        value=style.facecolor or default_color,
                        key=f"data_face_{label}",
                    )
                    edgecolor = st.color_picker(
                        "轮廓色",
                        value=style.edgecolor or default_color,
                        key=f"data_edge_{label}",
                    )
                    edge_width = st.number_input(
                        "轮廓线宽",
                        min_value=0.0,
                        max_value=20.0,
                        value=float(style.edge_width),
                        step=0.1,
                        key=f"data_edge_width_{label}",
                    )
                with third:
                    size = st.number_input(
                        "数据点大小",
                        min_value=1.0,
                        max_value=500.0,
                        value=float(style.size),
                        step=1.0,
                        key=f"data_size_{label}",
                    )
                controller.set_dataset_point_style(
                    label,
                    PointStyle(
                        marker=DATA_MARKER_OPTIONS[marker],
                        facecolor=facecolor,
                        edgecolor=edgecolor,
                        edge_width=float(edge_width),
                        size=float(size),
                    ),
                )


def _ask_plot_save_path() -> Path | None:
    """Use the native save dialog, matching project JSON saving behavior."""
    import tkinter as tk
    from tkinter import filedialog

    previous_path = Path(str(st.session_state.get(PLOT_SAVE_PATH, "")).strip() or ".")
    initial_dir = previous_path if previous_path.is_dir() else previous_path.parent
    initial_file = "petromodeler_plot.png" if previous_path.is_dir() else previous_path.name

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.update()
    try:
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="保存绘图",
            initialdir=str(initial_dir),
            initialfile=initial_file,
            defaultextension=".png",
            filetypes=[
                ("PNG 图像", "*.png"),
                ("JPEG 图像", "*.jpg *.jpeg"),
                ("SVG 矢量图", "*.svg"),
                ("PDF 文档", "*.pdf"),
                ("所有文件", "*.*"),
            ],
            confirmoverwrite=True,
        )
    finally:
        root.destroy()
    return Path(selected).expanduser() if selected else None


def _render_plot_download(controller: AppController, fig) -> None:
    st.caption("点击后在系统保存窗口中选择文件夹、文件名及 PNG/JPEG/SVG/PDF 格式。")
    if st.button("保存绘图到本地", key="save_plot_to_local"):
        try:
            selected_path = _ask_plot_save_path()
            if selected_path is not None:
                saved_path = controller.save_plot(fig, selected_path)
                st.session_state[PLOT_SAVE_PATH] = str(saved_path)
                st.session_state[PLOT_SAVE_MESSAGE] = ("success", f"绘图已保存到: {saved_path}")
        except Exception as exc:
            st.session_state[PLOT_SAVE_MESSAGE] = ("error", f"保存绘图失败: {exc}")

    if PLOT_SAVE_MESSAGE in st.session_state:
        level, message = st.session_state[PLOT_SAVE_MESSAGE]
        if level == "success":
            st.success(message)
        else:
            st.error(message)


def _ask_excel_save_path(default_filename: str) -> Path | None:
    """Open a native save dialog for an Excel export."""
    import tkinter as tk
    from tkinter import filedialog

    previous_path = Path(str(st.session_state.get(DETAIL_SAVE_PATH, "")).strip() or ".")
    initial_dir = previous_path if previous_path.is_dir() else previous_path.parent
    # Keep the last selected folder, but use the current export's meaningful
    # default name (all-results versus one-group results).
    initial_file = default_filename

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.update()
    try:
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="保存 Excel 计算结果",
            initialdir=str(initial_dir),
            initialfile=initial_file or default_filename,
            defaultextension=".xlsx",
            filetypes=[("Excel 工作簿", "*.xlsx"), ("所有文件", "*.*")],
            confirmoverwrite=True,
        )
    finally:
        root.destroy()
    return Path(selected).expanduser() if selected else None


def _save_excel_with_dialog(controller: AppController, data: bytes, default_filename: str) -> None:
    try:
        selected_path = _ask_excel_save_path(default_filename)
        if selected_path is None:
            return
        saved_path = controller.save_export_bytes(data, selected_path)
        st.session_state[DETAIL_SAVE_PATH] = str(saved_path)
        st.session_state[DETAIL_SAVE_MESSAGE] = ("success", f"计算结果已保存到: {saved_path}")
    except Exception as exc:
        st.session_state[DETAIL_SAVE_MESSAGE] = ("error", f"保存计算结果失败: {exc}")


def _show_detail_save_message() -> None:
    if DETAIL_SAVE_MESSAGE not in st.session_state:
        return
    level, message = st.session_state[DETAIL_SAVE_MESSAGE]
    if level == "success":
        st.success(message)
    else:
        st.error(message)


def render(controller: AppController, show_header: bool = True) -> None:
    if show_header:
        st.header("建模结果显示")

    # Plot settings
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        controller.set_plot_title(st.text_input("图标题", value=controller.state.plot.title, key="plot_title"))
    with col2:
        controller.set_plot_show_dataset(
            st.checkbox("显示用户数据", value=controller.state.plot.show_dataset, key="show_dataset")
        )
    with col3:
        controller.set_plot_show_legend(
            st.checkbox("显示图例", value=controller.state.plot.show_legend, key="show_legend")
        )

    if st.button("计算并绘图", key="run_all_plot"):
        controller.run_all()

    results = controller.current_results()
    if results:
        _render_style_editor(controller, results)
        fig = controller.build_plot(results)
        st.pyplot(fig, use_container_width=True)
        _render_plot_download(controller, fig)

        # Group messages
        for g in controller.state.groups:
            if not g.visible:
                continue
            if g.last_error:
                st.error(f"{g.name}: {g.last_error}")
            elif g.last_result and getattr(g.last_result, "warnings", None):
                for w in g.last_result.warnings:
                    st.warning(f"{g.name}: {w}")

        st.subheader("查看计算详情")
        detail_tables = list(controller.detail_tables_for_export())
        if detail_tables:
            all_excel_bytes = controller.export_grouped_detail_tables_excel(detail_tables)
            if st.button("下载全部参数组计算结果 Excel", key="dl_all_group_details"):
                _save_excel_with_dialog(controller, all_excel_bytes, "all_group_details.xlsx")

        for g in controller.state.groups:
            if not g.visible or not g.last_result or g.last_result.detail_table is None:
                continue
            with st.expander(f"{g.name} 计算详情", expanded=False):
                df = g.last_result.detail_table
                st.dataframe(df, use_container_width=True)
                excel_bytes = controller.export_detail_table_excel(df)
                if st.button("下载 Excel", key=f"dl_{g.group_id}"):
                    _save_excel_with_dialog(controller, excel_bytes, f"{g.name}_details.xlsx")
        _show_detail_save_message()
    else:
        st.info("点击“计算并绘图”以生成结果。")
