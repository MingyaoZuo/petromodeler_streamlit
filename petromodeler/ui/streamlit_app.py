"""Streamlit entry UI.

The UI is implemented as a set of pages under `petromodeler/ui/pages/`.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ..app.bootstrap import build_container
from ..infrastructure.persistence.project_store import ProjectStore
from .pages.axis_config_page import render as render_axis_config
from .pages.groups_page import render as render_groups
from .pages.data_import_page import render as render_data_import
from .pages.docs_page import render as render_docs


def _init_session() -> None:
    if "container" not in st.session_state:
        st.session_state.container = build_container(resources_dir=Path(__file__).resolve().parents[1] / "resources")
    if "project_store" not in st.session_state:
        st.session_state.project_store = ProjectStore()


def run() -> None:
    st.set_page_config(page_title="PetroModeler", layout="wide")
    _init_session()

    container = st.session_state.container
    controller = container.controller

    st.sidebar.title("PetroModeler")
    page = st.sidebar.radio("导航", ["轴配置", "参数组配置与绘图", "数据导入", "模型说明"], index=0)

    # Project save/load
    with st.sidebar.expander("项目保存/加载", expanded=False):
        store: ProjectStore = st.session_state.project_store
        if st.button("生成项目JSON"):
            st.session_state._project_json = store.dumps(controller.state)
        if "_project_json" in st.session_state:
            st.download_button(
                "下载项目JSON",
                data=st.session_state._project_json,
                file_name="petromodeler_project.json",
                mime="application/json",
            )
        upload = st.file_uploader("加载项目JSON", type=["json"], key="project_uploader")
        if upload is not None:
            try:
                text = upload.read().decode("utf-8")
                controller.state = store.loads(text)
                # keep container.state in sync
                container.state = controller.state
                st.success("项目已加载（数据表不会随项目保存/恢复）")
            except Exception as e:
                st.error(f"加载失败: {e}")

    if page == "轴配置":
        render_axis_config(controller)
    elif page == "参数组配置与绘图":
        render_groups(controller)
    elif page == "数据导入":
        render_data_import(controller)
    elif page == "模型说明":
        render_docs(controller)
