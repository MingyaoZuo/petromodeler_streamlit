from __future__ import annotations

import unittest

from petromodeler.application.state.app_state import AppState
from petromodeler.application.state.axis_state import AxisState
from petromodeler.application.state.group_state import GroupState
from petromodeler.application.state.dataset_state import DatasetState
from petromodeler.application.state.plot_state import CurveStyle, PlotState, PointStyle
from petromodeler.domain.expressions import Leaf
from petromodeler.domain.quantities import ElementConc, IsotopeValue


class AppStateRoundTripTest(unittest.TestCase):
    def test_snapshot_restore_round_trip(self) -> None:
        state = AppState()
        state.axis = AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(IsotopeValue(symbol="δ11B", kind="delta", carrier="B")))
        state.groups.append(
            GroupState(
                group_id="G1",
                name="Alpha",
                model_id="fc",
                params={"k": 1.23},
                visible=False,
            )
        )
        state.dataset = DatasetState(
            df=None,
            x_col="x",
            y_col="y",
            group_col="group",
            selected_group_values=["A", "B"],
        )
        state.plot = PlotState(
            title="My Plot",
            show_dataset=False,
            show_legend=True,
            x_axis_log_scale=True,
            y_axis_log_scale=True,
            annotated_points_by_group={"G1": [1, 3]},
            curve_styles_by_group={"G1": CurveStyle(line_color="#123456", marker="s")},
            dataset_point_styles_by_label={
                "A": PointStyle(
                    marker="D", facecolor="#abcdef", edgecolor="#010203", edge_width=2.5, size=44
                )
            },
        )

        restored = AppState.restore(state.snapshot())

        self.assertEqual(restored.axis.labels(), ("Sr (ppm)", "δ11B (‰)"))
        self.assertEqual(len(restored.groups), 1)
        self.assertEqual(restored.groups[0].group_id, "G1")
        self.assertEqual(restored.groups[0].name, "Alpha")
        self.assertEqual(restored.groups[0].model_id, "fc")
        self.assertEqual(restored.groups[0].params, {"k": 1.23})
        self.assertFalse(restored.groups[0].visible)
        self.assertEqual(restored.dataset.x_col, "x")
        self.assertEqual(restored.dataset.y_col, "y")
        self.assertEqual(restored.dataset.group_col, "group")
        self.assertEqual(restored.dataset.selected_group_values, ["A", "B"])
        self.assertEqual(restored.plot.title, "My Plot")
        self.assertFalse(restored.plot.show_dataset)
        self.assertTrue(restored.plot.show_legend)
        self.assertTrue(restored.plot.x_axis_log_scale)
        self.assertTrue(restored.plot.y_axis_log_scale)
        self.assertEqual(restored.plot.annotated_points_by_group, {"G1": [1, 3]})
        self.assertEqual(restored.plot.curve_styles_by_group["G1"].line_color, "#123456")
        self.assertEqual(restored.plot.curve_styles_by_group["G1"].marker, "s")
        self.assertEqual(restored.plot.dataset_point_styles_by_label["A"].marker, "D")
        self.assertEqual(restored.plot.dataset_point_styles_by_label["A"].edge_width, 2.5)
        self.assertEqual(restored.plot.dataset_point_styles_by_label["A"].size, 44)

    def test_restore_defaults_axis_number_format_for_older_projects(self) -> None:
        snapshot = AppState().snapshot()
        snapshot["plot"].pop("x_axis_log_scale")
        snapshot["plot"].pop("y_axis_log_scale")

        restored = AppState.restore(snapshot)

        self.assertFalse(restored.plot.x_axis_log_scale)
        self.assertFalse(restored.plot.y_axis_log_scale)


if __name__ == "__main__":
    unittest.main()
