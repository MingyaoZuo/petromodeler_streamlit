"""Inputs shared by devolatilization and mineral Rayleigh fractionation."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..parameters.derived import celsius_to_kelvin, fractionation_from_temperature
from ..parameters.keys import ParamKey
from ..parameters.specs import DerivedSpec, ParameterSchema, ParameterSpec
from ..quantities import IsotopeValue, quantity_id
from .utils import get_float, make_key


def fractionation_schema(
    group_id: str, model_id: str, q: IsotopeValue, default_delta: float = 8.33
) -> ParameterSchema:
    """Direct Delta or temperature equation, without choosing an output phase."""
    qid = quantity_id(q)

    def key(name: str) -> ParamKey:
        return ParamKey(group_id, model_id, "global", qid, name)

    mode_key = key("Delta_mode")
    specs = [
        ParameterSpec(
            key=mode_key,
            label=f"{q.symbol} Δ 输入方式",
            kind="choice",
            choices=["Direct Δ(‰)", "From T-equation"],
            default="Direct Δ(‰)",
            group="Isotope params",
            help=(
                "温度方程：1000 ln(α) = A*(1e6/T^2) + B*(1e3/T) + C\n"
                "Δ(‰) = 1000 ln(α)；α = exp(Δ/1000)\n"
                "T：温度（°C，后台计算时换算为 K）；A/B/C：经验系数"
            ),
        ),
        ParameterSpec(
            key=key("Delta"),
            label=f"{q.symbol} Δ (‰)",
            kind="float",
            default=default_delta,
            step=0.1,
            group="Isotope params",
            visible_if=(mode_key.to_string(), ["Direct Δ(‰)"]),
        ),
    ]
    for name in ("T", "A", "B", "C"):
        specs.append(
            ParameterSpec(
                key=key(name),
                label=f"{q.symbol} 温度 T (°C)" if name == "T" else f"系数 {name}",
                kind="float",
                default=600.0 if name == "T" else 0.0,
                step=10.0 if name == "T" else 0.1,
                group="Isotope params",
                visible_if=(mode_key.to_string(), ["From T-equation"]),
            )
        )
    return ParameterSchema(
        specs=specs,
        derived=[
            DerivedSpec(
                output_key=key("Delta_preview"),
                label=f"{q.symbol} 计算得到的 Δ (‰)",
                fn="fractionation_from_temperature:Delta",
                input_keys=[key(name).to_string() for name in ("A", "B", "C", "T")],
                unit="‰",
                group="Isotope params",
            )
        ],
    )


def fractionation_alpha(
    params: dict[str, Any], group_id: str, model_id: str, qid: str, default_delta: float = 8.33
) -> float:
    """Read the same alpha convention used by the original devolatilization model."""
    def param(name: str, default: float) -> float:
        return get_float(params, make_key(group_id, model_id, "global", qid, name), default)

    mode = params.get(make_key(group_id, model_id, "global", qid, "Delta_mode"), "Direct Δ(‰)")
    if mode == "From T-equation":
        _, delta = fractionation_from_temperature(
            param("A", 0.0), param("B", 0.0), param("C", 0.0), celsius_to_kelvin(param("T", 600.0))
        )
    else:
        delta = param("Delta", default_delta)
    return float(np.exp(delta / 1000.0))
