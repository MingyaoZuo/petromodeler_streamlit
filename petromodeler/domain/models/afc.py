"""AFC model (Assimilation-Fractional Crystallization / 同化-分离结晶).

This implementation follows the formulas as provided in `建模方法.md`.

Control variable
----------------
F: residual melt fraction (0,1]

Key parameters
--------------
- For each element (concentration): C0, Ca, D
- Global: r (assimilation/crystallization ratio)
- For each isotope ratio: IC0, ICa (requires the matching element concentration parameters)
- For each stable isotope delta: δ0, δa, and Δ (can be direct or computed from T)

Important
---------
The provided concentration equation in the summary contains a term (1 - F - Z),
which may become <=0 for some parameter choices. When this happens, the model
returns NaNs for the invalid region and reports warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

import numpy as np

from ..common.errors import ModelComputationError
from ..common.types import ControlGrid, ControlVarType
from ..parameters.keys import ParamKey
from ..parameters.specs import DerivedSpec, ParameterSpec, UISchema
from ..quantities import ElementConc, IsotopeValue, Quantity, quantity_id
from ..results import SimulationResult
from .base import IModel, ModelSpec
from .utils import get_bool, get_float, get_int, infer_group_id, make_key


class AFCModel(IModel):
    MODEL_ID = "afc"

    def spec(self) -> ModelSpec:
        return ModelSpec(id=self.MODEL_ID, name="AFC (同化-分离结晶)", control_var=ControlVarType.F)

    def required_schema(self, group_id: str, requested_quantities: Set[Quantity]) -> UISchema:
        specs: List[ParameterSpec] = []
        derived: List[DerivedSpec] = []

        # Grid
        specs.extend(
            [
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "F_min"),
                    label="F 最小值",
                    kind="float",
                    default=0.05,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.01,
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "F_max"),
                    label="F 最大值",
                    kind="float",
                    default=1.0,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.01,
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "n_points"),
                    label="点数",
                    kind="int",
                    default=50,
                    min_value=2,
                    max_value=2000,
                    step=1,
                    group="Grid",
                ),
                ParameterSpec(
                    key=ParamKey(group_id, self.MODEL_ID, "global", "", "descending"),
                    label="F 从大到小",
                    kind="bool",
                    default=True,
                    group="Grid",
                ),
            ]
        )

        # Global r
        specs.append(
            ParameterSpec(
                key=ParamKey(group_id, self.MODEL_ID, "global", "", "r"),
                label="r = m_a / m_c (同化/结晶速率比)",
                kind="float",
                default=0.2,
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                group="Global",
                help="注意：r 不能等于 1（会导致 Z 发散）",
            )
        )

        for q in requested_quantities:
            if isinstance(q, ElementConc):
                qid = quantity_id(q)
                elem = q.element
                specs.extend(
                    [
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "C0"),
                            label=f"{elem} 初始浓度 C0",
                            kind="float",
                            default=100.0,
                            min_value=0.0,
                            step=0.1,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "assimilant", qid, "Ca"),
                            label=f"{elem} 同化物质浓度 Ca",
                            kind="float",
                            default=200.0,
                            min_value=0.0,
                            step=0.1,
                            group="Element params",
                        ),
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "partition", qid, "D"),
                            label=f"{elem} 总分配系数 D",
                            kind="float",
                            default=1.0,
                            min_value=0.0,
                            step=0.01,
                            group="Element params",
                        ),
                    ]
                )

            elif isinstance(q, IsotopeValue):
                qid = quantity_id(q)
                # Isotope initial & assimilant values
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "IC0"),
                        label=f"{q.symbol} 初始值",
                        kind="float",
                        default=0.703 if q.kind == "ratio" else 0.0,
                        step=0.001,
                        group="Isotope params",
                    )
                )
                specs.append(
                    ParameterSpec(
                        key=ParamKey(group_id, self.MODEL_ID, "assimilant", qid, "ICa"),
                        label=f"{q.symbol} 同化端元值",
                        kind="float",
                        default=0.710 if q.kind == "ratio" else 0.0,
                        step=0.001,
                        group="Isotope params",
                    )
                )

                if q.kind == "delta":
                    # stable isotope uses Delta
                    mode_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta_mode")
                    specs.append(
                        ParameterSpec(
                            key=mode_key,
                            label=f"{q.symbol} 分馏因子输入方式",
                            kind="choice",
                            choices=["Direct Δ(‰)", "From T-equation"],
                            default="Direct Δ(‰)",
                            group="Isotope params",
                            help=(
                                "温度方程：1000 ln(α) = A*(1e6/T^2) + B*(1e3/T) + C\n"
                                "Δ(‰) = 1000 ln(α)；T：温度（K）；A/B/C：经验系数"
                            ),
                        )
                    )
                    delta_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta")
                    specs.append(
                        ParameterSpec(
                            key=delta_key,
                            label=f"{q.symbol} Δ (‰)",
                            kind="float",
                            default=-8.4,
                            step=0.1,
                            group="Isotope params",
                            visible_if=(mode_key.to_string(), ["Direct Δ(‰)"]),
                        )
                    )
                    # T-equation inputs (A,B,C,T)
                    A_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "A")
                    B_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "B")
                    C_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "C")
                    T_key = ParamKey(group_id, self.MODEL_ID, "global", qid, "T")
                    specs.extend(
                        [
                            ParameterSpec(
                                key=T_key,
                                label=f"{q.symbol} 温度 T (K)",
                                kind="float",
                                default=873.15,
                                step=1.0,
                                group="Isotope params",
                                visible_if=(mode_key.to_string(), ["From T-equation"]),
                            ),
                            ParameterSpec(
                                key=A_key,
                                label="系数 A",
                                kind="float",
                                default=0.0,
                                step=0.01,
                                group="Isotope params",
                                visible_if=(mode_key.to_string(), ["From T-equation"]),
                            ),
                            ParameterSpec(
                                key=B_key,
                                label="系数 B",
                                kind="float",
                                default=0.0,
                                step=0.01,
                                group="Isotope params",
                                visible_if=(mode_key.to_string(), ["From T-equation"]),
                            ),
                            ParameterSpec(
                                key=C_key,
                                label="系数 C",
                                kind="float",
                                default=0.0,
                                step=0.01,
                                group="Isotope params",
                                visible_if=(mode_key.to_string(), ["From T-equation"]),
                            ),
                        ]
                    )
                    # Derived Delta display
                    derived.append(
                        DerivedSpec(
                            output_key=ParamKey(group_id, self.MODEL_ID, "global", qid, "Delta_preview"),
                            label=f"{q.symbol} 计算得到的 Δ (‰)",
                            fn="fractionation_from_temperature:Delta",
                            input_keys=[
                                ParamKey(group_id, self.MODEL_ID, "global", qid, "A").to_string(),
                                ParamKey(group_id, self.MODEL_ID, "global", qid, "B").to_string(),
                                ParamKey(group_id, self.MODEL_ID, "global", qid, "C").to_string(),
                                ParamKey(group_id, self.MODEL_ID, "global", qid, "T").to_string(),
                            ],
                            unit="‰",
                            group="Isotope params",
                        )
                    )

                    # stable isotope initial & assimilant deltas
                    specs.append(
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "initial", qid, "delta0"),
                            label=f"{q.symbol} 初始 δ",
                            kind="float",
                            default=0.0,
                            step=0.1,
                            group="Isotope params",
                        )
                    )
                    specs.append(
                        ParameterSpec(
                            key=ParamKey(group_id, self.MODEL_ID, "assimilant", qid, "deltaa"),
                            label=f"{q.symbol} 同化端元 δ",
                            kind="float",
                            default=0.0,
                            step=0.1,
                            group="Isotope params",
                        )
                    )

        return UISchema(specs=specs, derived=derived)

    def simulate(self, requested_quantities: Set[Quantity], params: Dict[str, Any], grid: ControlGrid) -> SimulationResult:
        if grid.var != ControlVarType.F:
            raise ValueError("AFCModel requires a ControlGrid with var=F")

        group_id = infer_group_id(params, self.MODEL_ID)
        F = np.asarray(grid.values, dtype=float)

        r = get_float(params, make_key(group_id, self.MODEL_ID, "global", "", "r"))
        if abs(r - 1.0) < 1e-12:
            raise ModelComputationError("AFC: r cannot be 1 (Z becomes singular)")

        series_map: Dict[Quantity, np.ndarray] = {}
        warnings: List[str] = []

        # First compute all ElementConc quantities (needed by isotope formulas)
        for q in requested_quantities:
            if not isinstance(q, ElementConc):
                continue
            qid = quantity_id(q)
            C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "C0"))
            Ca = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", qid, "Ca"))
            D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", qid, "D"))

            # Z = (r + D - 1)/(r - 1)
            Z = (r + D - 1.0) / (r - 1.0)

            term = 1.0 - F - Z

            # Domain checks for power with non-integer exponents
            valid = term > 0
            if not np.all(valid):
                warnings.append(
                    f"AFC: (1 - F - Z) <= 0 for {q.element}; invalid region set to NaN. "
                    "Consider adjusting F range and/or r,D."
                )

            out = np.full_like(F, np.nan, dtype=float)
            # exponents
            exp1 = -r / (r + D - 1.0)
            exp2 = (r + D - 1.0) / (r - 1.0)

            # Implement as written in provided summary
            out[valid] = C0 * np.power(term[valid], exp1) + (r / (r + D - 1.0)) * (Ca / C0) * (
                1.0 - np.power(term[valid], exp2)
            )

            series_map[q] = out

        # Compute isotope quantities
        for q in requested_quantities:
            if not isinstance(q, IsotopeValue):
                continue

            qid = quantity_id(q)
            IC0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "IC0"))
            ICa = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", qid, "ICa"))

            if q.kind == "delta":
                delta0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", qid, "delta0"))
                deltaa = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", qid, "deltaa"))
                mode = params.get(make_key(group_id, self.MODEL_ID, "global", qid, "Delta_mode"), "Direct Δ(‰)")
                if mode == "From T-equation":
                    # preview already computed in UI; but we recompute to ensure correctness
                    A = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "A"), 0.0)
                    B = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "B"), 0.0)
                    C = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "C"), 0.0)
                    T = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "T"), 873.15)
                    from ..parameters.derived import fractionation_from_temperature

                    _, Delta = fractionation_from_temperature(A, B, C, T)
                else:
                    Delta = get_float(params, make_key(group_id, self.MODEL_ID, "global", qid, "Delta"), -8.4)

                # Need D to compute Z; assume carrier element or ask user to also include its D in requested_quantities
                carrier = q.carrier
                if not carrier:
                    # Without carrier, we cannot know which D to use. Use Z=1 as a fallback (warn).
                    warnings.append(f"AFC: stable isotope {q.symbol} missing carrier element; using Z=1 fallback")
                    Z_series = np.full_like(F, 1.0)
                else:
                    # build a synthetic ElementConc to get D for that element (in this group)
                    conc_qid = f"conc:melt:{carrier}"  # matches quantity_id(ElementConc(carrier))
                    D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", conc_qid, "D"), 1.0)
                    Z_val = (r + D - 1.0) / (r - 1.0)
                    Z_series = np.full_like(F, Z_val)

                term = 1.0 - F - Z_series
                valid = term > 0
                out = np.full_like(F, np.nan, dtype=float)
                out[valid] = ((deltaa - delta0 - Delta) * (r / (r - 1.0)) * term[valid]) + delta0
                series_map[q] = out
                continue

            # ratio/epsilon isotopes
            # Need element concentration params for the carrier element
            carrier = q.carrier
            if not carrier:
                warnings.append(f"AFC: isotope {q.symbol} missing carrier element; cannot compute; returning NaN")
                series_map[q] = np.full_like(F, np.nan, dtype=float)
                continue

            conc_qid = f"conc:melt:{carrier}"
            C0 = get_float(params, make_key(group_id, self.MODEL_ID, "initial", conc_qid, "C0"), np.nan)
            Ca = get_float(params, make_key(group_id, self.MODEL_ID, "assimilant", conc_qid, "Ca"), np.nan)
            D = get_float(params, make_key(group_id, self.MODEL_ID, "partition", conc_qid, "D"), np.nan)

            Z = (r + D - 1.0) / (r - 1.0)
            term = 1.0 - F - Z
            valid = term > 0
            out = np.full_like(F, np.nan, dtype=float)

            num = (r / (r - 1.0)) * (Ca / Z) * term * ICa + C0 * F * Z * IC0
            den = (r / (r - 1.0)) * (Ca / Z) * term + C0 * F * Z
            out[valid] = num[valid] / den[valid]
            series_map[q] = out

        return SimulationResult(grid=grid, series_map=series_map, warnings=warnings)
