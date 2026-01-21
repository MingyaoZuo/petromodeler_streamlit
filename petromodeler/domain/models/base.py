"""Model interface and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from ..common.types import ControlGrid, ControlVarType
from ..parameters.specs import ParameterSchema
from ..quantities import Quantity
from ..results import SimulationResult


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    control_var: ControlVarType
    description: str = ""


class IModel:
    """All models must implement this interface."""

    def spec(self) -> ModelSpec:
        raise NotImplementedError

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> ParameterSchema:
        """Return parameter schema (inputs + derived fields) required to run the model.

        group_id is used to build ParamKey so different groups don't collide.
        """
        raise NotImplementedError

    def simulate(
        self,
        requested_quantities: Set[Quantity],
        group_id: str,
        params: Dict[str, Any],
        grid: ControlGrid,
    ) -> SimulationResult:
        """Run the model for one explicit parameter group."""
        raise NotImplementedError
