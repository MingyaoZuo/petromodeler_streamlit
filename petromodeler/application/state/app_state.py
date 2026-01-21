"""Top-level application state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .axis_state import AxisState, default_axis_state
from .dataset_state import DatasetState
from .group_state import GroupState
from .plot_state import PlotState


@dataclass
class AppState:
    axis: AxisState = field(default_factory=default_axis_state)
    groups: List[GroupState] = field(default_factory=list)
    dataset: DatasetState = field(default_factory=DatasetState)
    plot: PlotState = field(default_factory=PlotState)

    def get_group(self, group_id: str) -> Optional[GroupState]:
        for g in self.groups:
            if g.group_id == group_id:
                return g
        return None

    def snapshot(self) -> Dict:
        """Serialize minimal state for project saving.

        Note: DataFrame is not saved; only mappings.
        """
        return {
            "axis": {"x": self.axis.x_expr.to_dict(), "y": self.axis.y_expr.to_dict()},
            "groups": [
                {
                    "id": g.group_id,
                    "name": g.name,
                    "model_id": g.model_id,
                    "params": dict(g.params),
                    "visible": g.visible,
                }
                for g in self.groups
            ],
            "dataset": {
                "x_col": self.dataset.x_col,
                "y_col": self.dataset.y_col,
                "group_col": self.dataset.group_col,
                "selected_group_values": self.dataset.selected_group_values,
            },
            "plot": {
                "title": self.plot.title,
                "show_dataset": self.plot.show_dataset,
                "show_legend": self.plot.show_legend,
                "annotated_points_by_group": dict(self.plot.annotated_points_by_group),
            },
            "version": 1,
        }

    @staticmethod
    def restore(snapshot: Dict) -> "AppState":
        from ...domain.expressions import expression_from_dict

        st = AppState()
        st.axis = AxisState(
            x_expr=expression_from_dict(snapshot["axis"]["x"]),
            y_expr=expression_from_dict(snapshot["axis"]["y"]),
        )
        st.groups = [
            GroupState(
                group_id=g["id"],
                name=g.get("name", g["id"]),
                model_id=g["model_id"],
                params=g.get("params", {}),
                visible=g.get("visible", True),
            )
            for g in snapshot.get("groups", [])
        ]
        ds = snapshot.get("dataset", {})
        selected_group_values = ds.get("selected_group_values")
        st.dataset = DatasetState(
            df=None,
            x_col=ds.get("x_col"),
            y_col=ds.get("y_col"),
            group_col=ds.get("group_col"),
            selected_group_values=(
                [str(value) for value in selected_group_values]
                if selected_group_values is not None
                else None
            ),
        )
        pl = snapshot.get("plot", {})
        st.plot = PlotState(
            title=pl.get("title", ""),
            show_dataset=pl.get("show_dataset", True),
            show_legend=pl.get("show_legend", True),
            annotated_points_by_group={
                str(group_id): [int(i) for i in indices]
                for group_id, indices in pl.get("annotated_points_by_group", {}).items()
            },
        )
        return st
