"""User dataset state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DatasetState:
    df: Optional[object] = None  # pandas DataFrame (kept as object to avoid hard domain dependency)
    x_col: Optional[str] = None
    y_col: Optional[str] = None
    group_col: Optional[str] = None

    def has_data(self) -> bool:
        return self.df is not None
