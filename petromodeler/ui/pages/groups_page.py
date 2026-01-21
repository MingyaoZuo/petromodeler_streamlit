"""Parameter groups page."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ...application.services.parameter_resolver import ensure_defaults, resolve_schema
from ...domain.models.registry import ModelRegistry
from ..widgets.parameter_form import render_parameter_form
from .plot_page import render as render_plot


def render(controller: AppController) -> None:
    rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
    active_group_id = st.session_state.get("_active_group_id")

    st.header("参数组管理")
    st.write("每个参数组独立选择模型与参数，可同时绘制多组结果。")

    left, right = st.columns([3, 2])
    with left:
        def _apply_group_name(_controller: AppController, _group_id: str, _widget_key: str) -> None:
            new_name = str(st.session_state.get(_widget_key, "")).strip()
            if not new_name:
                return
            g = _controller.state.get_group(_group_id)
            if g and new_name != g.name:
                _controller.set_group_name(_group_id, new_name)
                st.session_state.pop("_latest_results", None)
            st.session_state["_active_group_id"] = _group_id

        def _add_group(_controller: AppController, _model_id_to_use: str, _source_gid: str | None) -> None:
            prev_auto = st.session_state.get("_new_group_name_auto")
            new_name = st.session_state.get("new_group_name", "")

            new_group = _controller.add_group(name=new_name, model_id=_model_id_to_use)
            if _source_gid:
                src = _controller.state.get_group(_source_gid)
                if src:
                    _controller.set_group_params(new_group.group_id, dict(src.params))

            st.session_state.pop("_latest_results", None)
            st.session_state["_group_added"] = True
            st.session_state["_active_group_id"] = new_group.group_id

            next_auto = f"Group{len(_controller.state.groups)+1}"
            st.session_state["_new_group_name_auto"] = next_auto
            if new_name == prev_auto:
                st.session_state["new_group_name"] = next_auto

        # Add group
        model_specs = controller.registry.list_specs()
        model_labels = {s.name: s.id for s in model_specs}

        # "From" options
        from_labels = ["None"]
        from_map = {}
        for g in controller.state.groups:
            g_spec = controller.registry.get(g.model_id).spec()
            label = f"{g.name} | {g_spec.name}"
            from_labels.append(label)
            from_map[label] = g.group_id

        with st.expander("添加参数组", expanded=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                suggested_name = f"Group{len(controller.state.groups)+1}"
                st.session_state.setdefault("new_group_name", suggested_name)
                st.session_state.setdefault("_new_group_name_auto", st.session_state["new_group_name"])
                new_name = st.text_input("参数组名称", key="new_group_name")
            with col2:
                from_choice = st.selectbox("From", options=from_labels, index=0, key="new_group_from")
            with col3:
                source_gid = from_map.get(from_choice)
                if source_gid:
                    src = controller.state.get_group(source_gid)
                    src_spec = controller.registry.get(src.model_id).spec() if src else None
                    default_model_name = src_spec.name if src_spec else list(model_labels.keys())[0]
                    model_name = st.selectbox(
                        "模型",
                        options=list(model_labels.keys()),
                        index=list(model_labels.keys()).index(default_model_name) if default_model_name in model_labels else 0,
                        key="new_group_model",
                        disabled=True,
                    )
                    model_id_to_use = src.model_id if src else model_labels.get(model_name, list(model_labels.values())[0])
                else:
                    model_name = st.selectbox("模型", options=list(model_labels.keys()), index=0, key="new_group_model")
                    model_id_to_use = model_labels[model_name]
            with col4:
                st.button(
                    "添加",
                    key="add_group_btn",
                    on_click=_add_group,
                    args=(controller, model_id_to_use, source_gid),
                )

        if st.session_state.pop("_group_added", False):
            st.success("已添加参数组")

        # Existing groups
        if not controller.state.groups:
            st.info("尚无参数组，请先添加。")
        else:
            for g in controller.state.groups:
                model = controller.registry.get(g.model_id)
                spec = model.spec()
                with st.expander(f"{g.name}  |  {spec.name}", expanded=bool(active_group_id == g.group_id)):
                    top1, top2, top3, top4 = st.columns([2, 2, 1, 1], vertical_alignment="bottom")
                    with top1:
                        name_key = f"name_{g.group_id}"
                        st.text_input(
                            "名称",
                            value=g.name,
                            key=name_key,
                            on_change=_apply_group_name,
                            args=(controller, g.group_id, name_key),
                        )
                    with top2:
                        # model selection
                        current_name = spec.name
                        chosen_name = st.selectbox(
                            "模型",
                            options=list(model_labels.keys()),
                            index=list(model_labels.keys()).index(current_name) if current_name in model_labels else 0,
                            key=f"model_{g.group_id}",
                        )
                    with top3:
                        vis = st.checkbox("显示", value=g.visible, key=f"vis_{g.group_id}")
                        if vis != g.visible:
                            controller.set_group_visible(g.group_id, vis)
                            st.session_state["_active_group_id"] = g.group_id
                    with top4:
                        if st.button("删除", key=f"del_{g.group_id}"):
                            controller.delete_group(g.group_id)
                            st.session_state.pop("_latest_results", None)
                            if rerun:
                                rerun()

                    chosen_id = model_labels[chosen_name]
                    if chosen_id != g.model_id:
                        controller.update_group_model(g.group_id, chosen_id)
                        st.session_state.pop("_latest_results", None)
                        st.warning("模型已切换，参数已清空，请重新填写。")
                        st.session_state["_active_group_id"] = g.group_id

                    st.divider()

                    # schema + parameters (auto-save for reactive UI)
                    model = controller.registry.get(g.model_id)
                    schema = resolve_schema(model, g.group_id, controller.state.axis.x_expr, controller.state.axis.y_expr)
                    values = ensure_defaults(schema, g.params)

                    # Validation hints
                    report, _, _ = controller.sim.validate_group(g, controller.state.axis)
                    if report.errors:
                        st.warning(f"当前参数缺失/不合法: {len(report.errors)} 项")
                        with st.expander("查看参数问题", expanded=False):
                            for e in report.errors:
                                st.write(str(e))

                    updated = render_parameter_form(
                        schema=schema,
                        values=values,
                        derived_service=controller.derived,
                        key_prefix=g.group_id,
                    )
                    if updated != g.params:
                        controller.set_group_params(g.group_id, updated)
                        st.session_state.pop("_latest_results", None)
                        st.caption("参数已自动保存。")
                        st.session_state["_active_group_id"] = g.group_id

                    actions_left, actions_right = st.columns([1, 3], vertical_alignment="center")
                    with actions_left:
                        if st.button("立即计算该组", key=f"run_{g.group_id}"):
                            controller.run_group(g.group_id)
                            if g.last_error:
                                st.error(f"计算失败: {g.last_error}")
                            else:
                                st.success("计算完成")
                            st.session_state["_active_group_id"] = g.group_id

    with right:
        st.subheader("建模结果显示")
        render_plot(controller, show_header=False)
