"""Data import page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController


def _index_or_zero(options: list[str], value: str | None) -> int:
    if value is None:
        return 0
    try:
        return options.index(value)
    except Exception:
        return 0


def render(controller: AppController) -> None:
    st.header("用户数据导入")
    st.write("导入 Excel 后，可将数据点叠加到模型计算图上。")

    upload = st.file_uploader(
        "选择 Excel 文件",
        type=["xlsx", "xls"],
        key="data_excel_uploader",
    )

    if upload is not None:
        try:
            df = controller.load_dataset_excel(upload)
            st.success(f"已读取数据: {df.shape[0]} 行 × {df.shape[1]} 列")
        except Exception as e:
            st.error(f"读取失败: {e}")

    if controller.state.dataset.df is None:
        st.info("尚未加载数据。")
        return

    df = controller.state.dataset.df  # pandas DataFrame
    st.subheader("数据预览")
    st.dataframe(df.head(50), use_container_width=True)

    st.subheader("列映射")
    numeric_cols = controller.importer.infer_numeric_columns(df)
    all_cols = [str(c) for c in df.columns]

    if not numeric_cols:
        st.warning("未检测到数值列；仍可选择列，但绘图可能失败。")
        numeric_cols = all_cols

    x_options = ["(不选择)"] + numeric_cols
    y_options = ["(不选择)"] + numeric_cols
    group_options = ["(不分组)"] + all_cols

    col1, col2, col3 = st.columns(3)
    with col1:
        x_idx = _index_or_zero(x_options, controller.state.dataset.x_col)
        x_sel = st.selectbox("X 轴数据列", x_options, index=x_idx, key="data_x_col")
    with col2:
        y_idx = _index_or_zero(y_options, controller.state.dataset.y_col)
        y_sel = st.selectbox("Y 轴数据列", y_options, index=y_idx, key="data_y_col")
    with col3:
        g_idx = _index_or_zero(group_options, controller.state.dataset.group_col)
        g_sel = st.selectbox("分组列", group_options, index=g_idx, key="data_group_col")

    x_col = None if x_sel == "(不选择)" else x_sel
    y_col = None if y_sel == "(不选择)" else y_sel
    group_col = None if g_sel == "(不分组)" else g_sel

    if st.button("保存列映射", key="save_data_mapping"):
        controller.set_dataset_mapping(x_col=x_col, y_col=y_col, group_col=group_col)
        st.success("已保存列映射。")
