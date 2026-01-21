"""Plot UI state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlotState:
    title: str = ""
    show_dataset: bool = True
    show_legend: bool = True
