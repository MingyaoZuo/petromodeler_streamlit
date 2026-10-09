"""Streamlit widget: parameter form.

Renders ParameterSpec schemas into Streamlit input widgets.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

from ..session_keys import ACTIVE_GROUP_ID, ACTIVE_PARAMETER_SECTION
from ...domain.parameters.specs import DerivedSpec, ParameterSchema, ParameterSpec


def _is_visible(spec: ParameterSpec, values: Dict[str, Any]) -> bool:
    if spec.visible_if is None:
        return True
    dep_key, allowed = spec.visible_if
    return values.get(dep_key) in allowed


def _mark_active_group(group_id: str, section_name: str) -> None:
    st.session_state[ACTIVE_GROUP_ID] = group_id
    st.session_state[ACTIVE_PARAMETER_SECTION] = f"{group_id}:{section_name}"


ISOTOPE_NUMERIC_FIELDS = {
    "IC0",
    "ICa",
    "IC",
    "IC_melt",
    "Delta",
    "delta_i",
    "delta0",
    "deltaa",
    "delta_r_i",
    "delta_w_i",
    "A",
    "B",
    "C",
}


def _is_sr_isotope_ratio_parameter(spec: ParameterSpec) -> bool:
    if spec.key.name not in ISOTOPE_NUMERIC_FIELDS:
        return False
    parts = spec.key.quantity_id.split(":", 3)
    if len(parts) != 4:
        return False
    prefix, _context, kind, symbol = parts
    return prefix == "iso" and kind == "ratio" and "sr" in symbol.lower()


def _float_step(spec: ParameterSpec) -> float:
    if _is_sr_isotope_ratio_parameter(spec):
        return 0.001
    return float(spec.step) if spec.step is not None else 0.1


def _float_format(spec: ParameterSpec) -> str | None:
    if _is_sr_isotope_ratio_parameter(spec):
        return "%.4f"
    if spec.key.quantity_id.startswith("iso:") and spec.key.name in ISOTOPE_NUMERIC_FIELDS:
        return "%.2f"
    step = spec.step
    if step is None:
        return None
    text = f"{float(step):.10f}".rstrip("0").rstrip(".")
    if "." not in text:
        return "%.1f"
    decimals = min(len(text.split(".", 1)[1]), 10)
    return f"%.{decimals}f"


def _annotation_widget_key(group_id: str) -> str:
    return f"annotated_points_{group_id}"


def _annotation_point_label(detail_table: Any, index: int) -> str:
    control_col = detail_table.columns[0]
    value = float(detail_table[control_col].iloc[index])
    return f"{index}: {control_col}={value:.4g}"


def render_parameter_form(
    schema: ParameterSchema,
    values: Dict[str, Any],
    compute_derived: Callable[[DerivedSpec, Dict[str, Any]], Optional[float]],
    key_prefix: str,
    annotation_detail_table: Any | None = None,
    annotation_detail_table_factory: Callable[[Dict[str, Any]], Any | None] | None = None,
    annotated_point_indices: list[int] | None = None,
    on_annotation_points_change: Callable[[list[int]], None] | None = None,
) -> Dict[str, Any]:
    """Render a schema-driven parameter form and return updated values.

    The caller should store the returned dict into the corresponding GroupState.
    """

    out = dict(values)

    # group specs by UI group
    grouped: Dict[str, List[ParameterSpec]] = defaultdict(list)
    for spec in schema.specs:
        grouped[spec.group or "Parameters"].append(spec)

    # derived by group as well
    derived_grouped: Dict[str, List[DerivedSpec]] = defaultdict(list)
    for d in schema.derived:
        derived_grouped[d.group or "Parameters"].append(d)

    for group_name in grouped.keys() | derived_grouped.keys():
        section_key = f"{key_prefix}:{group_name}"
        is_active_section = st.session_state.get(ACTIVE_PARAMETER_SECTION) == section_key
        with st.expander(group_name, expanded=(group_name in ("Grid", "Global") or is_active_section)):
            # render inputs
            for spec in grouped.get(group_name, []):
                key_str = spec.key.to_string()
                if not _is_visible(spec, out):
                    continue

                widget_key = f"{key_prefix}:{key_str}"

                if spec.kind == "float":
                    out[key_str] = st.number_input(
                        spec.label,
                        value=float(out.get(key_str, spec.default) or 0.0),
                        min_value=spec.min_value,
                        max_value=spec.max_value,
                        step=_float_step(spec),
                        format=_float_format(spec),
                        key=widget_key,
                        help=spec.help or None,
                        on_change=_mark_active_group,
                        args=(key_prefix, group_name),
                    )
                elif spec.kind == "int":
                    out[key_str] = int(
                        st.number_input(
                            spec.label,
                            value=int(out.get(key_str, spec.default) or 0),
                            min_value=int(spec.min_value) if spec.min_value is not None else None,
                            max_value=int(spec.max_value) if spec.max_value is not None else None,
                            step=int(spec.step) if spec.step is not None else 1,
                            key=widget_key,
                            help=spec.help or None,
                            on_change=_mark_active_group,
                            args=(key_prefix, group_name),
                        )
                    )
                elif spec.kind == "choice":
                    choices = list(spec.choices or [])
                    if not choices:
                        choices = ["-"]
                    current = out.get(key_str, spec.default)
                    try:
                        idx = choices.index(current)
                    except Exception:
                        idx = 0
                    out[key_str] = st.selectbox(
                        spec.label,
                        choices,
                        index=idx,
                        key=widget_key,
                        help=spec.help or None,
                        on_change=_mark_active_group,
                        args=(key_prefix, group_name),
                    )
                elif spec.kind == "bool":
                    out[key_str] = st.checkbox(
                        spec.label,
                        value=bool(out.get(key_str, spec.default)),
                        key=widget_key,
                        on_change=_mark_active_group,
                        args=(key_prefix, group_name),
                    )
                elif spec.kind == "str":
                    out[key_str] = st.text_input(
                        spec.label,
                        value=str(out.get(key_str, spec.default) or ""),
                        key=widget_key,
                        on_change=_mark_active_group,
                        args=(key_prefix, group_name),
                    )
                else:
                    st.write(f"[Unsupported spec kind: {spec.kind}] {spec.label}")

            if group_name == "Grid" and on_annotation_points_change:
                if annotation_detail_table_factory:
                    annotation_detail_table = annotation_detail_table_factory(out)
                available_indices = list(range(len(annotation_detail_table))) if annotation_detail_table is not None else []
                current_indices = [i for i in (annotated_point_indices or []) if i in available_indices]
                selected_indices = st.multiselect(
                    "在图上显示并标注的数据点",
                    options=available_indices,
                    default=current_indices,
                    format_func=lambda index, detail_df=annotation_detail_table: _annotation_point_label(detail_df, index),
                    key=_annotation_widget_key(key_prefix),
                )
                on_annotation_points_change(list(selected_indices))

            # derived previews
            if derived_grouped.get(group_name):
                st.divider()
                st.caption("实时计算结果")
                for d in derived_grouped[group_name]:
                    val = compute_derived(d, out)
                    if val is None:
                        st.write(f"{d.label}: (无法计算)")
                    else:
                        st.write(f"{d.label}: **{val:.6g}** {d.unit}")
                    # store preview back into dict as well
                    out[d.output_key.to_string()] = val

    return out
