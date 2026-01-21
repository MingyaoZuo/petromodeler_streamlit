"""Plot service.

Creates matplotlib figures from simulation results and optional user dataset.
The UI (Streamlit) can render the figure via st.pyplot.
"""

from __future__ import annotations

from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ...domain.results import SimulationResult
from ..state.axis_state import AxisState
from ..state.dataset_state import DatasetState
from ..state.group_state import GroupState
from ..state.plot_state import PlotState


class PlotService:
    def build_figure(
        self,
        results_by_group: Dict[str, SimulationResult],
        groups: list[GroupState],
        axis: AxisState,
        dataset: DatasetState,
        plot_state: PlotState,
    ):
        fig, ax = plt.subplots()

        # curves
        for g in groups:
            if not g.visible:
                continue
            if g.group_id not in results_by_group:
                continue
            res = results_by_group[g.group_id]
            df = res.detail_table
            if df is None:
                continue
            x_col = axis.x_expr.label()
            y_col = axis.y_expr.label()
            if x_col in df.columns and y_col in df.columns:
                ax.plot(df[x_col].values, df[y_col].values, label=g.name)

        # dataset scatter
        if plot_state.show_dataset and dataset.df is not None and dataset.x_col and dataset.y_col:
            dfu: pd.DataFrame = dataset.df  # type: ignore[assignment]
            if dataset.group_col and dataset.group_col in dfu.columns:
                for key, sub in dfu.groupby(dataset.group_col):
                    ax.scatter(sub[dataset.x_col], sub[dataset.y_col], label=str(key), marker="o")
            else:
                ax.scatter(dfu[dataset.x_col], dfu[dataset.y_col], label="Data", marker="o")

        ax.set_xlabel(axis.x_expr.label())
        ax.set_ylabel(axis.y_expr.label())
        if plot_state.title:
            ax.set_title(plot_state.title)

        if plot_state.show_legend:
            ax.legend()

        ax.grid(True)
        fig.tight_layout()
        return fig
