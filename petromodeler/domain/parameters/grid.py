"""Shared control-grid parameter contract."""

from __future__ import annotations

from dataclasses import dataclass

from ..common.types import ControlVarType
from .keys import ParamKey
from .specs import ParameterSpec


GRID_MODE = "grid_mode"
GRID_N_POINTS = "n_points"
GRID_STEP = "grid_step"
GRID_DESCENDING = "descending"


@dataclass(frozen=True)
class ControlGridDefaults:
    min_value: float
    max_value: float
    step: float
    n_points: int = 50
    include_descending: bool = False
    descending: bool = False


CONTROL_GRID_DEFAULTS = {
    ControlVarType.F: ControlGridDefaults(
        min_value=0.05,
        max_value=1.0,
        step=0.01,
        include_descending=True,
        descending=True,
    ),
    ControlVarType.X: ControlGridDefaults(min_value=0.0, max_value=1.0, step=0.01),
    ControlVarType.N: ControlGridDefaults(min_value=0.0, max_value=3.0, step=0.1),
}


def control_grid_value_name(control_var: ControlVarType, suffix: str) -> str:
    return f"{control_var.value}_{suffix}"


def control_grid_key(group_id: str, model_id: str, name: str) -> str:
    return ParamKey(group_id, model_id, "global", "", name).to_string()


def control_grid_specs(group_id: str, model_id: str, control_var: ControlVarType) -> list[ParameterSpec]:
    defaults = CONTROL_GRID_DEFAULTS[control_var]
    mode_key = ParamKey(group_id, model_id, "global", "", GRID_MODE)
    min_name = control_grid_value_name(control_var, "min")
    max_name = control_grid_value_name(control_var, "max")

    specs = [
        ParameterSpec(
            key=ParamKey(group_id, model_id, "global", "", min_name),
            label=f"{control_var.value} 最小值",
            kind="float",
            default=defaults.min_value,
            min_value=0.0,
            max_value=1.0 if control_var in (ControlVarType.F, ControlVarType.X) else None,
            step=defaults.step,
            group="Grid",
        ),
        ParameterSpec(
            key=ParamKey(group_id, model_id, "global", "", max_name),
            label=f"{control_var.value} 最大值",
            kind="float",
            default=defaults.max_value,
            min_value=0.0,
            max_value=1.0 if control_var in (ControlVarType.F, ControlVarType.X) else None,
            step=defaults.step,
            group="Grid",
        ),
        ParameterSpec(
            key=mode_key,
            label="网格输入方式",
            kind="choice",
            choices=["By points", "By step"],
            default="By points",
            group="Grid",
        ),
        ParameterSpec(
            key=ParamKey(group_id, model_id, "global", "", GRID_N_POINTS),
            label="点数",
            kind="int",
            default=defaults.n_points,
            min_value=2,
            max_value=2000,
            step=1,
            group="Grid",
            visible_if=(mode_key.to_string(), ["By points"]),
        ),
        ParameterSpec(
            key=ParamKey(group_id, model_id, "global", "", GRID_STEP),
            label=f"{control_var.value} 步长",
            kind="float",
            default=defaults.step,
            min_value=0.000001,
            step=defaults.step,
            group="Grid",
            visible_if=(mode_key.to_string(), ["By step"]),
        ),
    ]

    if defaults.include_descending:
        specs.append(
            ParameterSpec(
                key=ParamKey(group_id, model_id, "global", "", GRID_DESCENDING),
                label=f"{control_var.value} 从大到小",
                kind="bool",
                default=defaults.descending,
                group="Grid",
            )
        )

    return specs
