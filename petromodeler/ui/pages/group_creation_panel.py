"""UI component for adding a new parameter group."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ..session_keys import ACTIVE_GROUP_ID, GROUP_ADDED, NEW_GROUP_NAME, NEW_GROUP_NAME_AUTO


def _add_group(controller: AppController, model_id_to_use: str, source_gid: str | None) -> None:
    prev_auto = st.session_state.get(NEW_GROUP_NAME_AUTO)
    new_name = str(st.session_state.get(NEW_GROUP_NAME, "")).strip()
    if not new_name:
        new_name = controller.get_next_group_name()

    try:
        new_group = controller.add_group(name=new_name, model_id=model_id_to_use)
    except ValueError as exc:
        st.session_state["add_group_error"] = str(exc)
        return
    if source_gid:
        controller.clone_group_params(source_gid, new_group.group_id)

    st.session_state[GROUP_ADDED] = True
    st.session_state[ACTIVE_GROUP_ID] = new_group.group_id

    next_auto = controller.get_next_group_name()
    st.session_state[NEW_GROUP_NAME_AUTO] = next_auto
    if new_name == prev_auto:
        st.session_state[NEW_GROUP_NAME] = next_auto


def render(controller: AppController) -> None:
    model_labels = controller.model_labels()
    model_names = list(model_labels.keys())

    if not model_names:
        st.info("暂无可用模型。")
        return

    from_labels = ["None"]
    from_map: dict[str, str] = {}
    for group in controller.state.groups:
        group_spec = controller.model_spec(group.model_id)
        label = f"{group.name} | {group_spec.name}"
        from_labels.append(label)
        from_map[label] = group.group_id

    with st.expander("添加参数组", expanded=True):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1:
            suggested_name = controller.get_next_group_name()
            st.session_state.setdefault(NEW_GROUP_NAME, suggested_name)
            st.session_state.setdefault(NEW_GROUP_NAME_AUTO, st.session_state[NEW_GROUP_NAME])
            if st.session_state.get(NEW_GROUP_NAME) == st.session_state.get(NEW_GROUP_NAME_AUTO):
                st.session_state[NEW_GROUP_NAME] = suggested_name
                st.session_state[NEW_GROUP_NAME_AUTO] = suggested_name
            st.text_input("参数组名称", key=NEW_GROUP_NAME)
        with col2:
            from_choice = st.selectbox("复制自", options=from_labels, index=0, key="new_group_from")
        with col3:
            source_gid = from_map.get(from_choice)
            if source_gid:
                source_group = controller.state.get_group(source_gid)
                source_spec = controller.model_spec(source_group.model_id) if source_group else None
                default_model_name = source_spec.name if source_spec else model_names[0]
                model_index = model_names.index(default_model_name) if default_model_name in model_labels else 0
                model_name = st.selectbox(
                    "模型",
                    options=model_names,
                    index=model_index,
                    key="new_group_model",
                    disabled=True,
                )
                model_id_to_use = source_group.model_id if source_group else model_labels[model_name]
            else:
                model_name = st.selectbox("模型", options=model_names, index=0, key="new_group_model")
                model_id_to_use = model_labels[model_name]
        with col4:
            st.button(
                "添加",
                key="add_group_btn",
                on_click=_add_group,
                args=(controller, model_id_to_use, source_gid),
            )
        if st.session_state.pop("add_group_error", None):
            st.error("参数组名称已存在，请使用不同名称。")
