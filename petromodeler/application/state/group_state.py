"""Parameter group state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ...domain.results import SimulationResult


@dataclass
class GroupState:
    group_id: str
    name: str
    model_id: str
    params: Dict[str, Any] = field(default_factory=dict)  # ParamKey.to_string() -> value
    visible: bool = True
    last_result: Optional[SimulationResult] = None
    last_error: Optional[str] = None

    def clear_result(self) -> None:
        self.last_result = None
        self.last_error = None
