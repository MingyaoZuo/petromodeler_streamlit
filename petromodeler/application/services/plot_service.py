"""Plot service.

Creates matplotlib figures from simulation results and optional user dataset.
The UI (Streamlit) can render the figure via st.pyplot.
"""

from __future__ import annotations

from typing import Any, Dict

import matplotlib

# Streamlit renders figures itself; an interactive desktop backend is neither
# needed nor available in all deployment environments.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..results import GroupRunResult
from ..state.axis_state import AxisState
from ..state.dataset_state import DatasetState
from ..state.group_state import GroupState
from ..state.plot_state import PlotState


class PlotService:
    def _annotation_label(self, df: pd.DataFrame, index: int) -> str:
        control_col = df.columns[0]
        value = df[control_col].iloc[index]
        try:
            value_text = f"{float(value):.4g}"
        except (TypeError, ValueError):
            value_text = str(value)
        return f"{control_col}={value_text}"

    def _draw_selected_points(
        self,
        ax: Any,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        selected_indices: list[int],
        color: Any,
    ) -> None:
        valid_indices = [index for index in selected_indices if 0 <= index < len(df)]
        if not valid_indices:
            return

        selected = df.iloc[valid_indices]
        ax.scatter(
            selected[x_col].values,
            selected[y_col].values,
            marker="o",
            s=56,
            facecolors="white",
            edgecolors=color,
            linewidths=1.5,
            zorder=4,
            label="_selected_points",
        )
        for index in valid_indices:
            row = df.iloc[index]
            ax.annotate(
                self._annotation_label(df, index),
                xy=(row[x_col], row[y_col]),
                xytext=(6, 6),
                textcoords="offset points",
                color=color,
                fontsize=9,
                zorder=5,
            )

    def build_figure(
        self,
        results_by_group: Dict[str, GroupRunResult],
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
                style = plot_state.curve_styles_by_group.get(g.group_id)
                line_kwargs: dict[str, Any] = {"label": g.name}
                if style is not None:
                    line_kwargs.update(
                        linestyle=style.line_style,
                        linewidth=style.line_width,
                        marker=style.marker or None,
                    )
                    if style.line_color:
                        line_kwargs["color"] = style.line_color
                    if style.marker_facecolor:
                        line_kwargs["markerfacecolor"] = style.marker_facecolor
                    if style.marker_edgecolor:
                        line_kwargs["markeredgecolor"] = style.marker_edgecolor
                (line,) = ax.plot(df[x_col].values, df[y_col].values, **line_kwargs)
                self._draw_selected_points(
                    ax=ax,
                    df=df,
                    x_col=x_col,
                    y_col=y_col,
                    selected_indices=plot_state.annotated_points_by_group.get(g.group_id, []),
                    color=line.get_color(),
                )

        # dataset scatter
        if plot_state.show_dataset and dataset.df is not None and dataset.x_col and dataset.y_col:
            dfu: pd.DataFrame = dataset.df  # type: ignore[assignment]
            has_xy = dataset.x_col in dfu.columns and dataset.y_col in dfu.columns
            if has_xy and dataset.group_col and dataset.group_col in dfu.columns:
                selected_values = (
                    set(dataset.selected_group_values)
                    if dataset.selected_group_values is not None
                    else None
                )
                for key, sub in dfu.groupby(dataset.group_col):
                    if selected_values is not None and str(key) not in selected_values:
                        continue
                    self._draw_dataset_points(
                        ax,
                        sub,
                        dataset.x_col,
                        dataset.y_col,
                        str(key),
                        plot_state,
                    )
            elif has_xy:
                self._draw_dataset_points(
                    ax, dfu, dataset.x_col, dataset.y_col, "Data", plot_state
                )

        ax.set_xlabel(axis.x_expr.label())
        ax.set_ylabel(axis.y_expr.label())
        if plot_state.x_axis_log_scale:
            ax.set_xscale("log")
        if plot_state.y_axis_log_scale:
            ax.set_yscale("log")
        if plot_state.title:
            ax.set_title(plot_state.title)

        handles, labels = ax.get_legend_handles_labels()
        visible_legend_items = [(handle, label) for handle, label in zip(handles, labels) if not label.startswith("_")]
        if plot_state.show_legend and visible_legend_items:
            handles, labels = zip(*visible_legend_items)
            ax.legend(handles, labels)

        ax.grid(True)
        fig.tight_layout()
        return fig

    @staticmethod
    def _draw_dataset_points(
        ax: Any,
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        label: str,
        plot_state: PlotState,
    ) -> None:
        style = plot_state.dataset_point_styles_by_label.get(label)
        scatter_kwargs: dict[str, Any] = {"label": label, "marker": "o"}
        if style is not None:
            scatter_kwargs.update(marker=style.marker, s=style.size, linewidths=style.edge_width)
            if style.facecolor:
                scatter_kwargs["facecolors"] = style.facecolor
            if style.edgecolor:
                scatter_kwargs["edgecolors"] = style.edgecolor
        ax.scatter(df[x_col], df[y_col], **scatter_kwargs)
