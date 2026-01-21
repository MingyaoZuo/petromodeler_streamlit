from __future__ import annotations

import unittest

from petromodeler.application.state.app_state import AppState
from petromodeler.application.state.axis_state import AxisState
from petromodeler.application.state.group_state import GroupState
from petromodeler.application.state.dataset_state import DatasetState
from petromodeler.application.state.plot_state import PlotState
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
        state.plot = PlotState(title="My Plot", show_dataset=False, show_legend=True, annotated_points_by_group={"G1": [1, 3]})

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
        self.assertEqual(restored.plot.annotated_points_by_group, {"G1": [1, 3]})


if __name__ == "__main__":
    unittest.main()
