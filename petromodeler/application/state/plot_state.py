"""Plot UI state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PlotState:
    title: str = ""
    show_dataset: bool = True
    show_legend: bool = True
    annotated_points_by_group: Dict[str, List[int]] = field(default_factory=dict)
