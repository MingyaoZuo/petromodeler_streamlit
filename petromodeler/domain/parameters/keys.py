"""Structured keys for parameters.

Using structured keys avoids variable-name collisions across parameter groups,
models and quantities.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamKey:
    group_id: str
    model_id: str
    role: str  # e.g., global/initial/assimilant/endmember_A/endmember_B/fluid/rock
    quantity_id: str  # quantity_id(...) or '' for pure-global params
    name: str  # e.g., C0, D, r, IC0

    def to_string(self) -> str:
        # A stable serialization format for project save/load.
        return f"{self.group_id}|{self.model_id}|{self.role}|{self.quantity_id}|{self.name}"

    def with_group_id(self, group_id: str) -> "ParamKey":
        return ParamKey(
            group_id=group_id,
            model_id=self.model_id,
            role=self.role,
            quantity_id=self.quantity_id,
            name=self.name,
        )

    @staticmethod
    def from_string(s: str) -> "ParamKey":
        parts = s.split("|")
        if len(parts) != 5:
            raise ValueError(f"Invalid ParamKey string: {s}")
        return ParamKey(*parts)
