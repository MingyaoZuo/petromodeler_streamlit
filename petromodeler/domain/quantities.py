"""Quantity definitions.

A Quantity represents a base variable that a model can compute as a function of
its control variable (F / X / N). Axis expressions (x/y) are composed from quantities.

Important: This module contains no Streamlit or file IO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Literal, Mapping, Optional, Sequence, Set, Tuple, Union

from .common.types import PhaseContext
from .common.units import NONE, PERMIL, PPM, RATIO, Unit


NormalizationSource = Literal["chondrite", "nasc", "primitive_mantle", "custom"]


@dataclass(frozen=True)
class NormalizationRef:
    source: NormalizationSource
    # For built-in sources, values can be empty (loaded from resources at runtime).
    # For custom, values should contain at least the required elements.
    values: Optional[Mapping[str, float]] = None


@dataclass(frozen=True)
class ElementConc:
    element: str
    context: PhaseContext = "melt"


@dataclass(frozen=True)
class IsotopeValue:
    """Isotope value.

    - kind='ratio' for e.g. 87Sr/86Sr
    - kind='delta' for e.g. δ11B
    - kind='epsilon' for e.g. εNd

    carrier is the element used as the mass-balance weight for mixing
    (needed mainly by mixing models). For many built-in isotope symbols, the UI
    can infer it.
    """

    symbol: str
    kind: Literal["ratio", "delta", "epsilon"]
    carrier: Optional[str] = None
    context: PhaseContext = "melt"


@dataclass(frozen=True)
class Anomaly:
    """REE anomaly (Eu or Ce)."""

    kind: Literal["Eu", "Ce"]
    normalization: NormalizationRef
    context: PhaseContext = "melt"


Quantity = Union[ElementConc, IsotopeValue, Anomaly]


def normalize_element_symbol(sym: str) -> str:
    """Normalize user input element symbol (very lightweight)."""

    s = (sym or "").strip()
    if not s:
        return s
    # Title-case: 'sr'->'Sr'
    return s[0].upper() + s[1:]


def quantity_id(q: Quantity) -> str:
    if isinstance(q, ElementConc):
        return f"conc:{q.context}:{normalize_element_symbol(q.element)}"
    if isinstance(q, IsotopeValue):
        return f"iso:{q.context}:{q.kind}:{q.symbol}"
    if isinstance(q, Anomaly):
        return f"anom:{q.context}:{q.kind}:{q.normalization.source}"
    raise TypeError(f"Unsupported quantity type: {type(q)}")


def quantity_unit(q: Quantity) -> Unit:
    if isinstance(q, ElementConc):
        return PPM
    if isinstance(q, IsotopeValue):
        if q.kind == "ratio":
            return RATIO
        return PERMIL
    if isinstance(q, Anomaly):
        return NONE
    return NONE


def format_quantity_label(q: Quantity) -> str:
    u = quantity_unit(q).label
    if isinstance(q, ElementConc):
        return f"{normalize_element_symbol(q.element)} ({u})" if u else normalize_element_symbol(q.element)
    if isinstance(q, IsotopeValue):
        return f"{q.symbol} ({u})" if u else q.symbol
    if isinstance(q, Anomaly):
        # commonly written as Eu/Eu* or Ce/Ce*
        base = f"{q.kind}/{q.kind}*"
        return f"{base} ({q.normalization.source})" if q.normalization.source else base
    return str(q)


def anomaly_required_elements(kind: Literal["Eu", "Ce"]) -> Tuple[str, ...]:
    """Return elements required to compute anomalies.

    - Eu anomaly uses Eu, Sm, Gd (Eu* ~ sqrt(Sm_N * Gd_N))
    - Ce anomaly uses Ce, La, Pr (Ce* ~ sqrt(La_N * Pr_N))
    """

    if kind == "Eu":
        return ("Eu", "Sm", "Gd")
    return ("Ce", "La", "Pr")


def expand_base_quantities(q: Quantity) -> Set[Quantity]:
    """Return base quantities needed to evaluate q.

    - ElementConc & IsotopeValue are base.
    - Anomaly depends on several ElementConc.
    """

    if isinstance(q, Anomaly):
        return {ElementConc(e, context=q.context) for e in anomaly_required_elements(q.kind)}
    return {q}
