"""Parameter specification schema.

This module defines the model-facing parameter contract: required inputs,
defaults, validation bounds, and lightweight presentation metadata. UI layers can
render controls from these specs, but the schema itself is not Streamlit-specific.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from .keys import ParamKey


ParamKind = Literal["float", "int", "str", "choice", "bool", "computed"]


@dataclass(frozen=True)
class ParameterSpec:
    key: ParamKey
    label: str
    kind: ParamKind = "float"
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[Sequence[Any]] = None
    unit: str = ""
    help: str = ""
    group: str = ""
    # simple condition: this spec applies only if a particular key equals one of these values
    visible_if: Optional[Tuple[str, Sequence[Any]]] = None


@dataclass(frozen=True)
class DerivedSpec:
    """Specification for a derived (computed) parameter value."""

    output_key: ParamKey
    label: str
    fn: str  # function id, implemented in domain.parameters.derived
    input_keys: List[str]  # list of ParamKey.to_string()
    unit: str = ""
    help: str = ""
    group: str = ""


@dataclass
class ParameterSchema:
    specs: List[ParameterSpec] = field(default_factory=list)
    derived: List[DerivedSpec] = field(default_factory=list)

    def all_keys(self) -> List[str]:
        keys = [s.key.to_string() for s in self.specs]
        keys += [d.output_key.to_string() for d in self.derived]
        return keys


# Backward-compatible alias for older callers. New code should use
# ParameterSchema to avoid implying that the domain layer owns UI rendering.
UISchema = ParameterSchema
