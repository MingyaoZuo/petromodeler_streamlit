"""Streamlit entry UI.

The UI is implemented as a set of pages under `petromodeler/ui/pages/`.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ..app.bootstrap import build_container
from .pages.axis_config_page import render as render_axis_config
from .pages.data_import_page import render as render_data_import
from .pages.docs_page import render as render_docs
from .pages.groups_page import render as render_groups
from .pages.project_sidebar import render as render_project_sidebar
from .session_keys import CONTAINER, PROJECT_SAVE_PATH


PAGES = {
    "轴配置": render_axis_config,
    "参数组配置与绘图": render_groups,
    "数据导入": render_data_import,
    "模型说明": render_docs,
}


def _init_session() -> None:
    if CONTAINER not in st.session_state:
        st.session_state[CONTAINER] = build_container(resources_dir=Path(__file__).resolve().parents[1] / "resources")
    if PROJECT_SAVE_PATH not in st.session_state:
        st.session_state[PROJECT_SAVE_PATH] = str(st.session_state[CONTAINER].project.default_save_path())


def run() -> None:
    st.set_page_config(page_title="PetroModeler", layout="wide")
    _init_session()

    container = st.session_state[CONTAINER]
    controller = container.controller

    st.sidebar.title("PetroModeler")
    page = st.sidebar.radio("导航", list(PAGES.keys()), index=0)
    render_project_sidebar(
        controller=controller,
        project=container.project,
        on_state_loaded=lambda: setattr(container, "state", controller.state),
    )

    PAGES[page](controller)
