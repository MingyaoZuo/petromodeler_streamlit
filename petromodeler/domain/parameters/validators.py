"""Parameter validation.

Validation runs in the domain layer so it can be reused by any UI framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..common.errors import ParameterValidationError
from .specs import ParameterSpec


def validate_params(specs: Iterable[ParameterSpec], values: Mapping[str, Any]) -> List[ParameterValidationError]:
    errors: List[ParameterValidationError] = []

    for spec in specs:
        key_str = spec.key.to_string()
        # visibility: if hidden, skip required checks
        if spec.visible_if is not None:
            dep_key, allowed = spec.visible_if
            dep_val = values.get(dep_key)
            if dep_val not in allowed:
                continue

        if spec.kind == "computed":
            continue

        if key_str not in values or values.get(key_str) is None or values.get(key_str) == "":
            errors.append(ParameterValidationError(key=key_str, message="Required value is missing"))
            continue

        v = values.get(key_str)
        if spec.kind in ("float", "int"):
            try:
                fv = float(v)
            except Exception:
                errors.append(ParameterValidationError(key=key_str, message="Value is not a number"))
                continue
            if spec.min_value is not None and fv < spec.min_value:
                errors.append(ParameterValidationError(key=key_str, message=f"Value < {spec.min_value}"))
            if spec.max_value is not None and fv > spec.max_value:
                errors.append(ParameterValidationError(key=key_str, message=f"Value > {spec.max_value}"))

    return errors
