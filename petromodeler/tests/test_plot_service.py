from __future__ import annotations

import unittest

import pandas as pd

from petromodeler.application.results import GroupRunResult
from petromodeler.application.services.plot_service import PlotService
from petromodeler.application.state.axis_state import AxisState
from petromodeler.application.state.dataset_state import DatasetState
from petromodeler.application.state.group_state import GroupState
from petromodeler.application.state.plot_state import PlotState
from petromodeler.domain.common.types import ControlGrid, ControlVarType
from petromodeler.domain.expressions import Leaf
from petromodeler.domain.quantities import ElementConc
from petromodeler.domain.results import SimulationResult


class PlotServiceTest(unittest.TestCase):
    def test_domain_simulation_result_has_no_detail_table_or_metadata(self) -> None:
        result = SimulationResult(
            grid=ControlGrid(ControlVarType.F, pd.Series([1.0]).to_numpy()),
            series_map={},
        )

        self.assertFalse(hasattr(result, "detail_table"))
        self.assertFalse(hasattr(result, "metadata"))

    def test_stale_dataset_mapping_is_ignored(self) -> None:
        dataset = DatasetState(
            df=pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]}),
            x_col="old_x",
            y_col="old_y",
        )

        fig = PlotService().build_figure(
            results_by_group={},
            groups=[],
            axis=AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))),
            dataset=dataset,
            plot_state=PlotState(show_dataset=True),
        )

        self.assertEqual(len(fig.axes[0].collections), 0)

    def test_selected_dataset_groups_are_plotted(self) -> None:
        dataset = DatasetState(
            df=pd.DataFrame(
                {
                    "x": [1.0, 2.0, 3.0],
                    "y": [10.0, 20.0, 30.0],
                    "group": ["A", "B", "A"],
                }
            ),
            x_col="x",
            y_col="y",
            group_col="group",
            selected_group_values=["B"],
        )

        fig = PlotService().build_figure(
            results_by_group={},
            groups=[],
            axis=AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))),
            dataset=dataset,
            plot_state=PlotState(show_dataset=True),
        )

        ax = fig.axes[0]
        self.assertEqual(len(ax.collections), 1)
        self.assertEqual(len(ax.collections[0].get_offsets()), 1)
        self.assertEqual(ax.get_legend_handles_labels()[1], ["B"])

    def test_selected_group_points_are_drawn_and_annotated(self) -> None:
        x_expr = Leaf(ElementConc("Sr"))
        y_expr = Leaf(ElementConc("Nd"))
        domain_result = SimulationResult(
            grid=ControlGrid(ControlVarType.F, pd.Series([1.0, 0.5, 0.1]).to_numpy()),
            series_map={},
        )
        result = GroupRunResult(
            domain_result=domain_result,
            detail_table=pd.DataFrame(
                {
                    "F": [1.0, 0.5, 0.1],
                    x_expr.label(): [10.0, 20.0, 30.0],
                    y_expr.label(): [1.0, 2.0, 3.0],
                }
            ),
            x_label=x_expr.label(),
            y_label=y_expr.label(),
            model_id="fc",
            group_id="G1",
        )

        fig = PlotService().build_figure(
            results_by_group={"G1": result},
            groups=[GroupState(group_id="G1", name="Group1", model_id="fc")],
            axis=AxisState(x_expr=x_expr, y_expr=y_expr),
            dataset=DatasetState(),
            plot_state=PlotState(show_dataset=False, annotated_points_by_group={"G1": [1]}),
        )

        ax = fig.axes[0]
        self.assertEqual(len(ax.collections), 1)
        self.assertEqual([text.get_text() for text in ax.texts], ["F=0.5"])


if __name__ == "__main__":
    unittest.main()
