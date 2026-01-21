"""Domain-layer common types.

This module must not import Streamlit/IO libraries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Literal, Mapping, Optional, Sequence, Tuple, Union

import numpy as np


Numeric = Union[int, float]
NumericArray = np.ndarray


# Context indicates which "phase" or "domain" a computed quantity belongs to.
# Keep this list extensible: new models can add new contexts without breaking old code.
PhaseContext = Literal[
    "melt",
    "rock",
    "fluid",
    "assimilant",
    "endmember_A",
    "endmember_B",
    "extracted_melt",
    "cumulate",
]


class ControlVarType(str, Enum):
    """Primary independent variable used to parametrize a model curve."""

    F = "F"  # residual melt fraction
    X = "X"  # mixing fraction
    N = "N"  # fluid/rock ratio


@dataclass(frozen=True)
class ControlGrid:
    """A 1D control variable grid used to run a model."""

    var: ControlVarType
    values: NumericArray

    def to_list(self) -> List[float]:
        return [float(x) for x in self.values]


def linspace_grid(start: float, stop: float, n: int, descending: bool = False) -> NumericArray:
    """Create a monotonic grid (inclusive)."""

    if n < 2:
        raise ValueError("n must be >= 2")
    arr = np.linspace(float(start), float(stop), int(n))
    if descending:
        arr = arr[::-1]
    return arr
