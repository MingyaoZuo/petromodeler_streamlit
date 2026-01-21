"""Streamlit widget: parameter form.

Renders ParameterSpec schemas into Streamlit input widgets.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import streamlit as st

from ...application.services.derived_service import DerivedService
from ...domain.parameters.specs import DerivedSpec, ParameterSpec, UISchema


def _is_visible(spec: ParameterSpec, values: Dict[str, Any]) -> bool:
    if spec.visible_if is None:
        return True
    dep_key, allowed = spec.visible_if
    return values.get(dep_key) in allowed


def _mark_active_group(group_id: str) -> None:
    st.session_state["_active_group_id"] = group_id


def render_parameter_form(
    schema: UISchema,
    values: Dict[str, Any],
    derived_service: DerivedService,
    key_prefix: str,
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
        with st.expander(group_name, expanded=(group_name in ("Grid", "Global"))):
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
                        step=0.1,
                        key=widget_key,
                        help=spec.help or None,
                        on_change=_mark_active_group,
                        args=(key_prefix,),
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
                            args=(key_prefix,),
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
                        args=(key_prefix,),
                    )
                elif spec.kind == "bool":
                    out[key_str] = st.checkbox(
                        spec.label,
                        value=bool(out.get(key_str, spec.default)),
                        key=widget_key,
                        on_change=_mark_active_group,
                        args=(key_prefix,),
                    )
                elif spec.kind == "str":
                    out[key_str] = st.text_input(
                        spec.label,
                        value=str(out.get(key_str, spec.default) or ""),
                        key=widget_key,
                        on_change=_mark_active_group,
                        args=(key_prefix,),
                    )
                else:
                    st.write(f"[Unsupported spec kind: {spec.kind}] {spec.label}")

            # derived previews
            if derived_grouped.get(group_name):
                st.divider()
                st.caption("实时计算结果")
                for d in derived_grouped[group_name]:
                    val = derived_service.compute(d, out)
                    if val is None:
                        st.write(f"{d.label}: (无法计算)")
                    else:
                        st.write(f"{d.label}: **{val:.6g}** {d.unit}")
                    # store preview back into dict as well
                    out[d.output_key.to_string()] = val

    return out
