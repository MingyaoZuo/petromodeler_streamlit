"""UI component for editing a single parameter group."""

from __future__ import annotations

import streamlit as st

from ...application.controllers.app_controller import AppController
from ..session_keys import ACTIVE_GROUP_ID
from ..widgets.parameter_form import render_parameter_form


def _activate_group(group_id: str) -> None:
    st.session_state[ACTIVE_GROUP_ID] = group_id


def _apply_group_name(controller: AppController, group_id: str, widget_key: str) -> None:
    new_name = str(st.session_state.get(widget_key, "")).strip()
    if not new_name:
        return

    group = controller.state.get_group(group_id)
    if group and new_name != group.name:
        try:
            controller.set_group_name(group_id, new_name)
        except ValueError:
            st.session_state[widget_key] = group.name
            st.session_state[f"{widget_key}_error"] = True
    _activate_group(group_id)


def render(
    controller: AppController,
    group_id: str,
    model_labels: dict[str, str],
    active_group_id: str | None,
    group_index: int,
    group_count: int,
    rerun,
) -> None:
    group = controller.state.get_group(group_id)
    if group is None:
        return

    spec = controller.model_spec(group.model_id)

    # `expanded` is the initial state of a Streamlit expander.  Keep this
    # value constant so the browser can retain each group's own open/closed
    # state across widget-triggered reruns.  Using ACTIVE_GROUP_ID here made
    # editing one group collapse other groups that the user had opened.
    with st.expander(f"{group.name} | {spec.name}", expanded=False):
        top1, top2, top3, top4, top5, top6, top7, top8 = st.columns(
            [2, 2, 1, 1, 0.65, 0.65, 0.65, 0.65],
            vertical_alignment="bottom",
        )
        with top1:
            name_key = f"name_{group.group_id}"
            st.text_input(
                "名称",
                value=group.name,
                key=name_key,
                on_change=_apply_group_name,
                args=(controller, group.group_id, name_key),
            )
            if st.session_state.pop(f"{name_key}_error", None):
                st.error("参数组名称已存在，请使用不同名称。")
        with top2:
            current_name = spec.name
            chosen_name = st.selectbox(
                "模型",
                options=list(model_labels.keys()),
                index=list(model_labels.keys()).index(current_name) if current_name in model_labels else 0,
                key=f"model_{group.group_id}",
            )
        with top3:
            visible = st.checkbox("显示", value=group.visible, key=f"vis_{group.group_id}")
            if visible != group.visible:
                controller.set_group_visible(group.group_id, visible)
                _activate_group(group.group_id)
        with top4:
            if st.button("删除", key=f"del_{group.group_id}"):
                controller.delete_group(group.group_id)
                if rerun:
                    rerun()
                return

        with top5:
            if st.button("⇈", key=f"move_top_{group.group_id}", disabled=group_index == 0, help="Move to top"):
                controller.move_group(group.group_id, -group_index)
                _activate_group(group.group_id)
                if rerun:
                    rerun()
                return
        with top6:
            if st.button("↑", key=f"move_up_{group.group_id}", disabled=group_index == 0, help="Move up"):
                controller.move_group(group.group_id, -1)
                _activate_group(group.group_id)
                if rerun:
                    rerun()
                return
        with top7:
            if st.button("↓", key=f"move_down_{group.group_id}", disabled=group_index == group_count - 1, help="Move down"):
                controller.move_group(group.group_id, 1)
                _activate_group(group.group_id)
                if rerun:
                    rerun()
                return
        with top8:
            if st.button("⇊", key=f"move_bottom_{group.group_id}", disabled=group_index == group_count - 1, help="Move to bottom"):
                controller.move_group(group.group_id, group_count - group_index - 1)
                _activate_group(group.group_id)
                if rerun:
                    rerun()
                return

        chosen_id = model_labels[chosen_name]
        if chosen_id != group.model_id:
            controller.update_group_model(group.group_id, chosen_id)
            spec = controller.model_spec(group.model_id)
            st.warning("模型已切换，参数已清空，请重新填写。")
            _activate_group(group.group_id)

        st.divider()

        if spec.description:
            st.caption(spec.description)

        form = controller.group_parameter_form(group.group_id)
        if form is None:
            return

        if form.validation_report.errors:
            st.warning(f"当前参数缺失/不合法: {len(form.validation_report.errors)} 项")
            with st.expander("查看参数问题", expanded=False):
                for error in form.validation_report.errors:
                    st.write(str(error))

        updated = render_parameter_form(
            schema=form.schema,
            values=form.values,
            compute_derived=controller.compute_derived_parameter,
            key_prefix=group.group_id,
            annotation_detail_table=form.annotation_detail_table,
            annotation_detail_table_factory=lambda values, g=group: controller._annotation_detail_table(g, values),
            annotated_point_indices=controller.state.plot.annotated_points_by_group.get(group.group_id, []),
            on_annotation_points_change=lambda indices, gid=group.group_id: controller.set_group_annotation_points(gid, indices),
        )
        if updated != group.params:
            controller.set_group_params(group.group_id, updated)
            st.caption("参数已自动保存。")
            _activate_group(group.group_id)

        actions_left, _actions_right = st.columns([1, 3], vertical_alignment="center")
        with actions_left:
            if st.button("立即计算该组", key=f"run_{group.group_id}"):
                controller.run_group(group.group_id)
                if group.last_error:
                    st.error(f"计算失败: {group.last_error}")
                else:
                    st.success("计算完成")
                _activate_group(group.group_id)
