from __future__ import annotations

import unittest

import pandas as pd

from petromodeler.application.results import GroupRunResult
from petromodeler.application.services.plot_service import PlotService
from petromodeler.application.state.axis_state import AxisState
from petromodeler.application.state.dataset_state import DatasetState
from petromodeler.application.state.group_state import GroupState
from petromodeler.application.state.plot_state import CurveStyle, PlotState, PointStyle
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

    def test_curve_and_dataset_legend_styles_are_applied(self) -> None:
        x_expr = Leaf(ElementConc("Sr"))
        y_expr = Leaf(ElementConc("Nd"))
        result = GroupRunResult(
            domain_result=SimulationResult(
                grid=ControlGrid(ControlVarType.F, pd.Series([1.0, 0.5]).to_numpy()),
                series_map={},
            ),
            detail_table=pd.DataFrame(
                {x_expr.label(): [10.0, 20.0], y_expr.label(): [1.0, 2.0]}
            ),
            x_label=x_expr.label(),
            y_label=y_expr.label(),
            model_id="fc",
            group_id="G1",
        )
        state = PlotState(
            show_dataset=True,
            curve_styles_by_group={
                "G1": CurveStyle(
                    line_color="#112233",
                    line_style="--",
                    line_width=2.5,
                    marker="s",
                    marker_facecolor="#aabbcc",
                    marker_edgecolor="#010203",
                )
            },
            dataset_point_styles_by_label={
                "Data": PointStyle(
                    marker="D", facecolor="#ff0000", edgecolor="#0000ff", edge_width=2.5, size=64
                )
            },
        )

        fig = PlotService().build_figure(
            results_by_group={"G1": result},
            groups=[GroupState(group_id="G1", name="Group1", model_id="fc")],
            axis=AxisState(x_expr=x_expr, y_expr=y_expr),
            dataset=DatasetState(
                df=pd.DataFrame({"x": [4.0], "y": [5.0]}), x_col="x", y_col="y"
            ),
            plot_state=state,
        )

        ax = fig.axes[0]
        curve = ax.lines[0]
        points = ax.collections[0]
        self.assertEqual(curve.get_color(), "#112233")
        self.assertEqual(curve.get_linestyle(), "--")
        self.assertEqual(curve.get_marker(), "s")
        self.assertEqual(curve.get_linewidth(), 2.5)
        self.assertEqual(points.get_sizes().tolist(), [64])
        self.assertEqual(points.get_linewidths().tolist(), [2.5])

    def test_selected_axes_use_logarithmic_scale(self) -> None:
        dataset = DatasetState(
            df=pd.DataFrame({"x": [1000.0, 2000.0], "y": [3.0, 4.0]}),
            x_col="x",
            y_col="y",
        )

        fig = PlotService().build_figure(
            results_by_group={},
            groups=[],
            axis=AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))),
            dataset=dataset,
            plot_state=PlotState(
                show_dataset=True,
                x_axis_log_scale=True,
                y_axis_log_scale=False,
            ),
        )

        self.assertEqual(fig.axes[0].get_xscale(), "log")
        self.assertEqual(fig.axes[0].get_yscale(), "linear")

    def test_selected_axes_use_scientific_number_format(self) -> None:
        dataset = DatasetState(
            df=pd.DataFrame({"x": [1000.0, 2000.0], "y": [3.0, 4.0]}),
            x_col="x",
            y_col="y",
        )

        fig = PlotService().build_figure(
            results_by_group={},
            groups=[],
            axis=AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))),
            dataset=dataset,
            plot_state=PlotState(
                show_dataset=True,
                x_axis_scientific=True,
                y_axis_scientific=False,
            ),
        )

        x_formatter = fig.axes[0].xaxis.get_major_formatter()
        y_formatter = fig.axes[0].yaxis.get_major_formatter()
        self.assertTrue(x_formatter.get_useMathText())
        self.assertEqual(x_formatter._powerlimits, (0, 0))
        self.assertFalse(y_formatter.get_useMathText())

    def test_log_scale_and_scientific_settings_can_coexist(self) -> None:
        for x_log, y_log in ((True, False), (False, True), (True, True)):
            with self.subTest(x_log=x_log, y_log=y_log):
                fig = PlotService().build_figure(
                    results_by_group={},
                    groups=[],
                    axis=AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))),
                    dataset=DatasetState(
                        df=pd.DataFrame({"x": [1000.0, 2000.0], "y": [3.0, 4.0]}),
                        x_col="x",
                        y_col="y",
                    ),
                    plot_state=PlotState(
                        x_axis_log_scale=x_log,
                        y_axis_log_scale=y_log,
                        x_axis_scientific=True,
                        y_axis_scientific=True,
                    ),
                )
                ax = fig.axes[0]
                self.assertEqual(ax.get_xscale(), "log" if x_log else "linear")
                self.assertEqual(ax.get_yscale(), "log" if y_log else "linear")
                # Rendering also exercises the selected tick formatters.
                fig.canvas.draw()


if __name__ == "__main__":
    unittest.main()
