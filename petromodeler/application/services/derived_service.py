"""Derived field computation service."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...domain.parameters.derived import compute_derived
from ...domain.parameters.specs import DerivedSpec


class DerivedService:
    def compute(self, spec: DerivedSpec, values: Dict[str, Any]) -> Optional[float]:
        # map input names expected by compute_derived
        # For the temperature equation we use A,B,C,T keys in order.
        try:
            inputs = {}
            # derive key names from last path segment of ParamKey string
            for key_str in spec.input_keys:
                # ParamKey format: group|model|role|qid|name
                name = key_str.split("|")[-1]
                if name in ("A", "B", "C", "T"):
                    inputs[name] = float(values.get(key_str, 0.0))
            return float(compute_derived(spec.fn, inputs))
        except Exception:
            return None
