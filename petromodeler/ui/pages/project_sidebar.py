"""Project save/load sidebar component."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

from ...application.controllers.app_controller import AppController
from ...application.services.project_service import ProjectService
from ..session_keys import PROJECT_SAVE_MESSAGE, PROJECT_SAVE_PATH, PROJECT_UPLOAD_DIGEST


def _project_save_path(project: ProjectService) -> Path:
    raw_path = str(st.session_state.get(PROJECT_SAVE_PATH, "")).strip()
    return Path(raw_path).expanduser() if raw_path else project.default_save_path()


def _show_project_message() -> None:
    if PROJECT_SAVE_MESSAGE not in st.session_state:
        return

    level, message = st.session_state[PROJECT_SAVE_MESSAGE]
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    else:
        st.info(message)


def _save_project_to_server_path(project: ProjectService, project_json: str) -> None:
    try:
        saved_path = project.save_text(project_json, _project_save_path(project))
        st.session_state[PROJECT_SAVE_PATH] = str(saved_path)
        st.session_state[PROJECT_SAVE_MESSAGE] = ("success", f"Project saved to: {saved_path}")
    except Exception as exc:
        st.session_state[PROJECT_SAVE_MESSAGE] = ("error", f"Save failed: {exc}")


def render(
    controller: AppController,
    project: ProjectService,
    on_state_loaded: Callable[[], None] | None = None,
) -> None:
    with st.sidebar.expander("项目保存/加载", expanded=False):
        project_json = project.dumps(controller.state)
        st.download_button(
            label="下载项目 JSON",
            data=project_json.encode("utf-8"),
            file_name=project.default_filename,
            mime="application/json",
            key="download_project_json",
        )

        st.text_input("服务器保存路径", value=str(_project_save_path(project)), key=PROJECT_SAVE_PATH)
        if st.button("保存到服务器路径", key="save_project_to_server_path"):
            _save_project_to_server_path(project, project_json)

        _show_project_message()

        upload = st.file_uploader("加载 JSON", type=["json"], key="project_uploader")
        if upload is not None:
            try:
                payload = upload.getvalue()
                digest = project.payload_digest(payload)
                if st.session_state.get(PROJECT_UPLOAD_DIGEST) != digest:
                    controller.replace_state(project.loads(payload.decode("utf-8")), preserve_dataset=True)
                    if on_state_loaded is not None:
                        on_state_loaded()
                    st.session_state[PROJECT_UPLOAD_DIGEST] = digest
                    st.success("项目已成功加载。")
            except Exception as exc:
                st.error(f"加载失败: {exc}")
        else:
            st.session_state.pop(PROJECT_UPLOAD_DIGEST, None)
