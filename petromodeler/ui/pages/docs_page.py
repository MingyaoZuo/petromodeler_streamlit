"""Model documentation page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...application.controllers.app_controller import AppController


def render(controller: AppController) -> None:
    st.header("模型说明")

    docs_path = Path(__file__).resolve().parents[2] / "resources" / "docs" / "models.md"
    if docs_path.exists():
        st.markdown(docs_path.read_text(encoding="utf-8"), unsafe_allow_html=False)
    else:
        st.info("未找到内置说明文档。")

    raw_path = Path(__file__).resolve().parents[2] / "resources" / "docs" / "建模方法.md"
    if raw_path.exists():
        with st.expander("查看原始建模方法.md", expanded=False):
            st.markdown(raw_path.read_text(encoding="utf-8"), unsafe_allow_html=False)
