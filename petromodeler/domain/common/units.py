"""Lightweight unit helpers.

We do not implement a full unit system here; we only store human-facing unit labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Unit:
    label: str


PPM = Unit("ppm")
PERMIL = Unit("‰")
RATIO = Unit("ratio")
NONE = Unit("")


def unit_or_empty(unit: Optional[Unit]) -> str:
    return unit.label if unit else ""
