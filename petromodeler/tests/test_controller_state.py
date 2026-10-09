from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from petromodeler.application.controllers.app_controller import AppController
from petromodeler.application.services.derived_service import DerivedService
from petromodeler.application.services.export_service import ExportService
from petromodeler.application.services.import_service import ImportService
from petromodeler.application.services.normalization_service import NormalizationService
from petromodeler.application.services.plot_service import PlotService
from petromodeler.application.services.simulation_service import SimulationService
from petromodeler.application.state.app_state import AppState
from petromodeler.application.state.axis_state import AxisState
from petromodeler.application.state.dataset_state import DatasetState
from petromodeler.domain.expressions import Leaf
from petromodeler.domain.models.fc import FCModel
from petromodeler.domain.models.mm import MMModel
from petromodeler.domain.models.water_rock import WaterRockModel
from petromodeler.domain.parameters.keys import ParamKey
from petromodeler.domain.models.registry import ModelRegistry
from petromodeler.domain.quantities import ElementConc


def make_controller() -> AppController:
    resources_dir = Path(__file__).resolve().parents[1] / "resources"
    registry = ModelRegistry()
    return AppController(
        state=AppState(),
        registry=registry,
        simulation_service=SimulationService(registry),
        plot_service=PlotService(),
        import_service=ImportService(),
        export_service=ExportService(),
        normalization_service=NormalizationService(resources_dir=resources_dir / "normalization"),
        derived_service=DerivedService(),
    )


class ControllerStateMutationTest(unittest.TestCase):
    def test_set_axis_clears_cached_group_results(self) -> None:
        controller = make_controller()
        group = controller.add_group("Group 1", "fc")
        group.last_result = object()
        group.last_error = "boom"

        controller.set_axis(AxisState(x_expr=Leaf(ElementConc("Sr")), y_expr=Leaf(ElementConc("Nd"))))

        self.assertIsNone(group.last_result)
        self.assertIsNone(group.last_error)

    def test_replace_state_preserves_imported_dataset_mapping_and_group_selection(self) -> None:
        controller = make_controller()
        original_df = pd.DataFrame(
            {
                "x": [1.0, 2.0],
                "y": [3.0, 4.0],
                "group": ["A", "B"],
            }
        )
        controller.state.dataset = DatasetState(
            df=original_df,
            x_col="x",
            y_col="y",
            group_col="group",
            selected_group_values=["B"],
        )
        loaded_state = AppState()
        loaded_state.dataset = DatasetState(
            df=None,
            x_col="missing_x",
            y_col="y",
            group_col="missing_group",
            selected_group_values=["A"],
        )

        controller.replace_state(loaded_state)

        self.assertIs(controller.state.dataset.df, original_df)
        self.assertEqual(controller.state.dataset.x_col, "x")
        self.assertEqual(controller.state.dataset.y_col, "y")
        self.assertEqual(controller.state.dataset.group_col, "group")
        self.assertEqual(controller.state.dataset.selected_group_values, ["B"])

    def test_update_group_model_clears_params_and_result(self) -> None:
        controller = make_controller()
        group = controller.add_group("Group 1", "fc")
        group.params = {"k": 1}
        group.last_result = object()

        controller.update_group_model(group.group_id, "mm")

        self.assertEqual(group.model_id, "mm")
        self.assertEqual(group.params, {})
        self.assertIsNone(group.last_result)

    def test_next_group_name_uses_first_available_group_number(self) -> None:
        controller = make_controller()
        controller.add_group("Group1", "fc")

        self.assertEqual(controller.get_next_group_name(), "Group2")

        controller.add_group("Custom", "fc")
        self.assertEqual(controller.get_next_group_name(), "Group2")

    def test_add_group_rejects_duplicate_names(self) -> None:
        controller = make_controller()
        controller.add_group("Group1", "fc")

        with self.assertRaises(ValueError):
            controller.add_group("Group1", "fc")

    def test_set_group_name_rejects_duplicate_names(self) -> None:
        controller = make_controller()
        first = controller.add_group("Group1", "fc")
        second = controller.add_group("Group2", "fc")

        with self.assertRaises(ValueError):
            controller.set_group_name(second.group_id, "Group1")

        self.assertEqual(first.name, "Group1")
        self.assertEqual(second.name, "Group2")

    def test_move_group_reorders_groups_within_bounds(self) -> None:
        controller = make_controller()
        first = controller.add_group("Group1", "fc")
        second = controller.add_group("Group2", "fc")
        third = controller.add_group("Group3", "fc")
        fourth = controller.add_group("Group4", "fc")

        controller.move_group(second.group_id, -1)

        self.assertEqual(
            [g.group_id for g in controller.state.groups],
            [second.group_id, first.group_id, third.group_id, fourth.group_id],
        )

        controller.move_group(fourth.group_id, -3)

        self.assertEqual(
            [g.group_id for g in controller.state.groups],
            [fourth.group_id, second.group_id, first.group_id, third.group_id],
        )

        controller.move_group(second.group_id, 2)

        self.assertEqual(
            [g.group_id for g in controller.state.groups],
            [fourth.group_id, first.group_id, third.group_id, second.group_id],
        )

        controller.move_group(fourth.group_id, -1)

        self.assertEqual(
            [g.group_id for g in controller.state.groups],
            [fourth.group_id, first.group_id, third.group_id, second.group_id],
        )

    def test_set_group_params_copies_input_and_preserves_existing_result(self) -> None:
        controller = make_controller()
        group = controller.add_group("Group 1", "fc")
        existing_result = object()
        group.last_result = existing_result
        payload = {"a": 1}

        controller.set_group_params(group.group_id, payload)
        payload["a"] = 2

        self.assertEqual(group.params, {"a": 1})
        self.assertIs(group.last_result, existing_result)
        self.assertEqual(controller.current_results(), {group.group_id: existing_result})

    def test_annotation_detail_table_uses_current_grid_when_cached_grid_is_stale(self) -> None:
        controller = make_controller()
        controller.registry.register(FCModel())
        group = controller.add_group("Group 1", "fc")
        group.params = {
            ParamKey(group.group_id, "fc", "global", "", "F_min").to_string(): 0.2,
            ParamKey(group.group_id, "fc", "global", "", "F_max").to_string(): 0.6,
            ParamKey(group.group_id, "fc", "global", "", "n_points").to_string(): 3,
            ParamKey(group.group_id, "fc", "global", "", "descending").to_string(): False,
        }
        group.last_result = SimpleNamespace(
            detail_table=pd.DataFrame({"F": [0.2, 0.6], "x": [10.0, 20.0], "y": [1.0, 2.0]})
        )

        detail_table = controller._annotation_detail_table(group, group.params)

        self.assertIsNotNone(detail_table)
        self.assertEqual([round(v, 6) for v in detail_table["F"].tolist()], [0.2, 0.4, 0.6])

    def test_build_grid_supports_step_mode_for_f(self) -> None:
        controller = make_controller()
        group = controller.add_group("Group 1", "fc")
        group.params = {
            ParamKey(group.group_id, "fc", "global", "", "F_min").to_string(): 0.0,
            ParamKey(group.group_id, "fc", "global", "", "F_max").to_string(): 0.05,
            ParamKey(group.group_id, "fc", "global", "", "grid_mode").to_string(): "By step",
            ParamKey(group.group_id, "fc", "global", "", "grid_step").to_string(): 0.02,
            ParamKey(group.group_id, "fc", "global", "", "descending").to_string(): False,
        }

        grid = controller.sim.build_grid(FCModel(), group)

        self.assertEqual([round(v, 6) for v in grid.to_list()], [0.0, 0.02, 0.04, 0.05])

    def test_build_grid_uses_exact_group_grid_keys(self) -> None:
        controller = make_controller()
        group = controller.add_group("Group 1", "fc")
        group.params = {
            ParamKey("other_group", "fc", "global", "", "F_min").to_string(): 0.0,
            ParamKey(group.group_id, "fc", "global", "", "F_max").to_string(): 0.2,
            ParamKey(group.group_id, "fc", "global", "", "n_points").to_string(): 2,
            ParamKey(group.group_id, "fc", "global", "", "descending").to_string(): False,
        }

        grid = controller.sim.build_grid(FCModel(), group)

        self.assertEqual([round(v, 6) for v in grid.to_list()], [0.05, 0.2])

    def test_build_grid_supports_step_mode_for_x_and_n(self) -> None:
        controller = make_controller()
        mm_group = controller.add_group("MM", "mm")
        mm_group.params = {
            ParamKey(mm_group.group_id, "mm", "global", "", "X_min").to_string(): 0.0,
            ParamKey(mm_group.group_id, "mm", "global", "", "X_max").to_string(): 0.05,
            ParamKey(mm_group.group_id, "mm", "global", "", "grid_mode").to_string(): "By step",
            ParamKey(mm_group.group_id, "mm", "global", "", "grid_step").to_string(): 0.02,
        }
        wr_group = controller.add_group("WR", "water_rock")
        wr_group.params = {
            ParamKey(wr_group.group_id, "water_rock", "global", "", "N_min").to_string(): 0.0,
            ParamKey(wr_group.group_id, "water_rock", "global", "", "N_max").to_string(): 0.25,
            ParamKey(wr_group.group_id, "water_rock", "global", "", "grid_mode").to_string(): "By step",
            ParamKey(wr_group.group_id, "water_rock", "global", "", "grid_step").to_string(): 0.1,
        }

        x_grid = controller.sim.build_grid(MMModel(), mm_group)
        n_grid = controller.sim.build_grid(WaterRockModel(), wr_group)

        self.assertEqual([round(v, 6) for v in x_grid.to_list()], [0.0, 0.02, 0.04, 0.05])
        self.assertEqual([round(v, 6) for v in n_grid.to_list()], [0.0, 0.1, 0.2, 0.25])

    def test_plot_state_setters_update_state(self) -> None:
        controller = make_controller()
        controller.set_plot_title("Demo")
        controller.set_plot_show_dataset(False)
        controller.set_plot_show_legend(False)
        controller.set_plot_axis_log_scale(True, False)
        controller.set_plot_axis_scientific(True, False)

        self.assertEqual(controller.state.plot.title, "Demo")
        self.assertFalse(controller.state.plot.show_dataset)
        self.assertFalse(controller.state.plot.show_legend)
        self.assertTrue(controller.state.plot.x_axis_log_scale)
        self.assertFalse(controller.state.plot.y_axis_log_scale)
        self.assertTrue(controller.state.plot.x_axis_scientific)
        self.assertFalse(controller.state.plot.y_axis_scientific)

    def test_clone_group_params_remaps_group_id_in_keys(self) -> None:
        controller = make_controller()
        source = controller.add_group("Source", "fc")
        target = controller.add_group("Target", "fc")

        source_key = ParamKey(source.group_id, "fc", "global", "", "F_min").to_string()
        source.params = {source_key: 0.12}

        controller.clone_group_params(source.group_id, target.group_id)

        target_key = ParamKey(target.group_id, "fc", "global", "", "F_min").to_string()
        self.assertEqual(target.params, {target_key: 0.12})

    def test_clone_group_params_rejects_malformed_keys(self) -> None:
        controller = make_controller()
        source = controller.add_group("Source", "fc")
        target = controller.add_group("Target", "fc")
        source.params = {"legacy_F_min": 0.12}

        with self.assertRaises(ValueError):
            controller.clone_group_params(source.group_id, target.group_id)

    def test_clone_group_params_rejects_foreign_group_keys(self) -> None:
        controller = make_controller()
        source = controller.add_group("Source", "fc")
        target = controller.add_group("Target", "fc")
        source.params = {
            ParamKey("other_group", "fc", "global", "", "F_min").to_string(): 0.12,
        }

        with self.assertRaises(ValueError):
            controller.clone_group_params(source.group_id, target.group_id)

    def test_run_group_uses_group_id_context_not_param_key_inference(self) -> None:
        controller = make_controller()
        controller.registry.register(FCModel())
        group = controller.add_group("Group 1", "fc")
        quantity = ElementConc("Sr")
        controller.set_axis(AxisState(x_expr=Leaf(quantity), y_expr=Leaf(quantity)))
        group.params = {
            ParamKey("other_group", "fc", "initial", "conc:melt:Sr", "C0").to_string(): 99.0,
            ParamKey("other_group", "fc", "partition", "conc:melt:Sr", "D").to_string(): 1.0,
            ParamKey(group.group_id, "fc", "global", "", "F_min").to_string(): 0.5,
            ParamKey(group.group_id, "fc", "global", "", "F_max").to_string(): 1.0,
            ParamKey(group.group_id, "fc", "global", "", "n_points").to_string(): 2,
            ParamKey(group.group_id, "fc", "global", "", "descending").to_string(): False,
            ParamKey(group.group_id, "fc", "initial", "conc:melt:Sr", "C0").to_string(): 2.0,
            ParamKey(group.group_id, "fc", "partition", "conc:melt:Sr", "D").to_string(): 1.0,
        }

        result = controller.run_group(group.group_id)

        self.assertIsNotNone(result)
        self.assertEqual([round(v, 6) for v in result.series_map[quantity].tolist()], [2.0, 2.0])

    def test_load_dataset_excel_normalizes_columns_and_drops_missing_mapping(self) -> None:
        controller = make_controller()
        controller.state.dataset.x_col = "1"
        controller.state.dataset.y_col = "missing_y"
        controller.state.dataset.group_col = "missing_group"
        controller.state.dataset.selected_group_values = ["A"]
        payload = BytesIO()
        pd.DataFrame({1: [1.0, 2.0], "y": [3.0, 4.0]}).to_excel(payload, index=False)
        payload.seek(0)

        df = controller.load_dataset_excel(payload)

        self.assertEqual(list(df.columns), ["1", "y"])
        self.assertEqual(controller.state.dataset.x_col, "1")
        self.assertIsNone(controller.state.dataset.y_col)
        self.assertIsNone(controller.state.dataset.group_col)
        self.assertIsNone(controller.state.dataset.selected_group_values)

    def test_set_dataset_mapping_filters_selected_group_values(self) -> None:
        controller = make_controller()
        controller.state.dataset.df = pd.DataFrame(
            {
                "x": [1.0, 2.0, 3.0],
                "y": [10.0, 20.0, 30.0],
                "group": ["A", "B", "A"],
            }
        )

        controller.set_dataset_mapping(
            x_col="x",
            y_col="y",
            group_col="group",
            selected_group_values=["B", "missing"],
        )

        self.assertEqual(controller.state.dataset.selected_group_values, ["B"])


if __name__ == "__main__":
    unittest.main()
