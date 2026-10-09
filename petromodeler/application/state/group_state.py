"""Parameter group state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ...domain.parameters.keys import ParamKey
from ..results import GroupRunResult


@dataclass
class GroupState:
    group_id: str
    name: str
    model_id: str
    params: Dict[str, Any] = field(default_factory=dict)  # ParamKey.to_string() -> value
    visible: bool = True
    last_result: Optional[GroupRunResult] = None
    last_error: Optional[str] = None

    @staticmethod
    def restore(snapshot: Dict[str, Any], project_version: int = 1) -> "GroupState":
        """Keep pre-split Rayleigh groups on their original degassing formulas."""
        model_id = snapshot["model_id"]
        params = dict(snapshot.get("params", {}))
        if project_version < 2 and model_id == "rayleigh":
            model_id = "degassing"
            migrated: Dict[str, Any] = {}
            for key_string, value in params.items():
                try:
                    key = ParamKey.from_string(key_string)
                except ValueError:
                    # Preserve unrelated legacy keys rather than dropping data.
                    migrated[key_string] = value
                    continue
                if key.model_id == "rayleigh":
                    key = ParamKey(key.group_id, "degassing", key.role, key.quantity_id, key.name)
                migrated[key.to_string()] = value
            params = migrated
        return GroupState(
            group_id=snapshot["id"],
            name=snapshot.get("name", snapshot["id"]),
            model_id=model_id,
            params=params,
            visible=snapshot.get("visible", True),
        )

    def clear_result(self) -> None:
        self.last_result = None
        self.last_error = None
