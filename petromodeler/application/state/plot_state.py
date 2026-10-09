"""Plot UI state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CurveStyle:
    """Visual settings for one parameter-group curve."""

    line_color: Optional[str] = None
    line_style: str = "-"
    line_width: float = 1.5
    marker: str = ""
    marker_facecolor: Optional[str] = None
    marker_edgecolor: Optional[str] = None


@dataclass
class PointStyle:
    """Visual settings for one user-data legend item."""

    marker: str = "o"
    facecolor: Optional[str] = None
    edgecolor: Optional[str] = None
    edge_width: float = 1.0
    size: float = 36.0


@dataclass
class PlotState:
    title: str = ""
    show_dataset: bool = True
    show_legend: bool = True
    x_axis_log_scale: bool = False
    y_axis_log_scale: bool = False
    x_axis_scientific: bool = False
    y_axis_scientific: bool = False
    annotated_points_by_group: Dict[str, List[int]] = field(default_factory=dict)
    curve_styles_by_group: Dict[str, CurveStyle] = field(default_factory=dict)
    dataset_point_styles_by_label: Dict[str, PointStyle] = field(default_factory=dict)
