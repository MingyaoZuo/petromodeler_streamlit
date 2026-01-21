"""Derived parameter calculations.

This module provides formula helpers for parameters that can be computed from other
user inputs (e.g., isotopic fractionation factor from temperature).

Equation supported:
    1000 ln(alpha) = A*(1e6/T^2) + B*(1e3/T) + C

We treat:
- alpha = exp((1000 ln(alpha))/1000)
- Delta(‰) = 1000 ln(alpha)
"""

from __future__ import annotations

import math
from typing import Dict, Mapping, Tuple


def celsius_to_kelvin(T_C: float) -> float:
    return float(T_C) + 273.15


def fractionation_from_temperature(A: float, B: float, C: float, T_K: float) -> Tuple[float, float]:
    """Return (alpha, Delta_permil).

    Parameters
    ----------
    A, B, C : coefficients
    T_K     : temperature in Kelvin
    """
    expr = A * (1e6 / (T_K**2)) + B * (1e3 / T_K) + C
    alpha = math.exp(expr / 1000.0)
    Delta = expr
    return alpha, Delta


DERIVED_FUNCTIONS = {
    "fractionation_from_temperature": fractionation_from_temperature,
}


def compute_derived(fn_id: str, inputs: Mapping[str, float]) -> float:
    """Compute a single derived value.

    Convention:
    - If fn returns a tuple, caller chooses the needed component.
    Here we implement two common outputs using fn_id suffix:
        - '...:alpha'
        - '...:Delta'
    """
    if ":" in fn_id:
        base, which = fn_id.split(":", 1)
    else:
        base, which = fn_id, "value"

    if base not in DERIVED_FUNCTIONS:
        raise KeyError(f"Unknown derived function: {fn_id}")

    # Only support this equation for now
    if base == "fractionation_from_temperature":
        A = float(inputs.get("A"))
        B = float(inputs.get("B"))
        C = float(inputs.get("C"))
        T_K = celsius_to_kelvin(float(inputs.get("T")))
        alpha, Delta = fractionation_from_temperature(A, B, C, T_K)
        if which.lower() == "alpha":
            return float(alpha)
        if which.lower() == "delta":
            return float(Delta)
        # default: Delta
        return float(Delta)

    # fallback for future
    out = DERIVED_FUNCTIONS[base](**inputs)
    if isinstance(out, tuple):
        return float(out[0])
    return float(out)
