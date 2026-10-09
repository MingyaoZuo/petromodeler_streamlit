from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from petromodeler.domain.common.types import ControlVarType
from petromodeler.domain.parameters.grid import GRID_STEP, control_grid_specs
from petromodeler.domain.parameters.keys import ParamKey
from petromodeler.domain.parameters.specs import ParameterSchema, ParameterSpec
from petromodeler.ui.session_keys import ACTIVE_GROUP_ID, ACTIVE_PARAMETER_SECTION
from petromodeler.ui.widgets.parameter_form import render_parameter_form


class _DummyExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _compute_derived(_spec, _values):
    return None


class ParameterFormTest(unittest.TestCase):
    def test_float_input_uses_parameter_spec_step(self) -> None:
        calls = []

        def number_input(label, **kwargs):
            calls.append(kwargs)
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            session_state={},
        )
        key = ParamKey("G1", "rayleigh", "global", "iso:melt:delta:delta11B", "T")
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=key,
                    label="delta11B 温度 T (°C)",
                    kind="float",
                    default=600.0,
                    step=10.0,
                    group="Isotope params",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        self.assertEqual(calls[0]["step"], 10.0)

    def test_isotope_float_input_uses_step_0_1_and_two_decimals(self) -> None:
        calls = []

        def number_input(label, **kwargs):
            calls.append(kwargs)
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            session_state={},
        )
        key = ParamKey("G1", "fc", "initial", "iso:melt:delta:delta11B", "IC0")
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=key,
                    label="delta11B 初始值",
                    kind="float",
                    default=0.0,
                    step=0.1,
                    group="Isotope params",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        self.assertEqual(calls[0]["step"], 0.1)
        self.assertEqual(calls[0]["format"], "%.2f")

    def test_sr_isotope_ratio_input_uses_step_0_001_and_four_decimals(self) -> None:
        calls = []

        def number_input(label, **kwargs):
            calls.append(kwargs)
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            session_state={},
        )
        key = ParamKey("G1", "fc", "initial", "iso:melt:ratio:87Sr/86Sr", "IC0")
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=key,
                    label="87Sr/86Sr initial value",
                    kind="float",
                    default=0.703,
                    step=0.1,
                    group="Isotope params",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        self.assertEqual(calls[0]["step"], 0.001)
        self.assertEqual(calls[0]["format"], "%.4f")

    def test_n_grid_step_input_uses_step_0_01_and_two_decimals(self) -> None:
        calls = []

        def number_input(label, **kwargs):
            calls.append(kwargs)
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            selectbox=lambda label, options, **kwargs: "By step",
            session_state={},
        )
        schema = ParameterSchema(specs=control_grid_specs("G1", "water_rock", ControlVarType.N))

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        grid_step_call = next(call for call in calls if call["key"].endswith(f"|{GRID_STEP}"))
        self.assertEqual(grid_step_call["step"], 0.01)
        self.assertEqual(grid_step_call["format"], "%.2f")

    def test_changed_parameter_section_stays_expanded_after_rerun(self) -> None:
        expanders = []

        def expander(label, **kwargs):
            expanders.append((label, kwargs))
            return _DummyExpander()

        def number_input(label, **kwargs):
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=expander,
            number_input=number_input,
            session_state={ACTIVE_PARAMETER_SECTION: "G1:Element params"},
        )
        key = ParamKey("G1", "fc", "initial", "conc:melt:Sr", "C0")
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=key,
                    label="Sr 初始浓度 C0",
                    kind="float",
                    default=100.0,
                    step=10.0,
                    group="Element params",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        self.assertEqual(expanders[0][0], "Element params")
        self.assertTrue(expanders[0][1]["expanded"])

    def test_active_group_does_not_expand_inactive_parameter_sections(self) -> None:
        expanded_by_label = {}

        def expander(label, **kwargs):
            expanded_by_label[label] = kwargs["expanded"]
            return _DummyExpander()

        def number_input(label, **kwargs):
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=expander,
            number_input=number_input,
            session_state={
                ACTIVE_GROUP_ID: "G1",
                ACTIVE_PARAMETER_SECTION: "G1:Element params",
            },
        )
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=ParamKey("G1", "fc", "initial", "conc:melt:Sr", "C0"),
                    label="Sr 初始浓度 C0",
                    kind="float",
                    default=100.0,
                    group="Element params",
                ),
                ParameterSpec(
                    key=ParamKey("G1", "fc", "initial", "iso:melt:delta:delta11B", "IC0"),
                    label="delta11B 初始值",
                    kind="float",
                    default=0.0,
                    group="Isotope params",
                ),
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")

        self.assertTrue(expanded_by_label["Element params"])
        self.assertFalse(expanded_by_label["Isotope params"])

    def test_input_change_marks_active_parameter_section(self) -> None:
        calls = []
        session_state = {}

        def number_input(label, **kwargs):
            calls.append(kwargs)
            return kwargs["value"]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            session_state=session_state,
        )
        key = ParamKey("G1", "fc", "initial", "conc:melt:Sr", "C0")
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=key,
                    label="Sr 初始浓度 C0",
                    kind="float",
                    default=100.0,
                    group="Element params",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(schema, {}, _compute_derived, "G1")
            calls[0]["on_change"](*calls[0]["args"])

        self.assertEqual(session_state[ACTIVE_GROUP_ID], "G1")
        self.assertEqual(session_state[ACTIVE_PARAMETER_SECTION], "G1:Element params")

    def test_annotation_selector_renders_inside_grid_section(self) -> None:
        selected = []
        multiselect_calls = []

        def number_input(label, **kwargs):
            return kwargs["value"]

        def multiselect(label, **kwargs):
            multiselect_calls.append((label, kwargs))
            return [1]

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            multiselect=multiselect,
            session_state={},
        )
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=ParamKey("G1", "fc", "global", "", "F_min"),
                    label="F min",
                    kind="float",
                    default=0.0,
                    group="Grid",
                )
            ]
        )
        detail_table = pd.DataFrame({"F": [1.0, 0.5], "x": [10.0, 20.0], "y": [1.0, 2.0]})

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(
                schema,
                {},
                _compute_derived,
                "G1",
                annotation_detail_table=detail_table,
                annotated_point_indices=[0],
                on_annotation_points_change=lambda indices: selected.extend(indices),
            )

        self.assertEqual(multiselect_calls[0][0], "在图上显示并标注的数据点")
        self.assertEqual(multiselect_calls[0][1]["default"], [0])
        self.assertEqual(selected, [1])

    def test_annotation_selector_uses_current_grid_values_after_step_input_change(self) -> None:
        multiselect_calls = []
        step_key = ParamKey("G1", "water_rock", "global", "", "grid_step").to_string()

        def number_input(label, **kwargs):
            if kwargs["key"].endswith("|grid_step"):
                return 0.03
            return kwargs["value"]

        def multiselect(label, **kwargs):
            multiselect_calls.append((label, kwargs))
            return []

        def annotation_detail_table_factory(current_values):
            step = current_values[step_key]
            return pd.DataFrame({"N": [0.0, step, step * 2]})

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            selectbox=lambda label, options, **kwargs: "By step",
            multiselect=multiselect,
            session_state={},
        )
        schema = ParameterSchema(specs=control_grid_specs("G1", "water_rock", ControlVarType.N))

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(
                schema,
                {step_key: 0.02},
                _compute_derived,
                "G1",
                annotation_detail_table=pd.DataFrame({"N": [0.0, 0.02, 0.04]}),
                annotation_detail_table_factory=annotation_detail_table_factory,
                on_annotation_points_change=lambda indices: None,
            )

        label_for_second_point = multiselect_calls[0][1]["format_func"](1)
        self.assertIn("N=0.03", label_for_second_point)

    def test_annotation_selector_renders_without_detail_table(self) -> None:
        selected = []
        multiselect_calls = []

        def number_input(label, **kwargs):
            return kwargs["value"]

        def multiselect(label, **kwargs):
            multiselect_calls.append((label, kwargs))
            return []

        fake_st = SimpleNamespace(
            expander=lambda *args, **kwargs: _DummyExpander(),
            number_input=number_input,
            multiselect=multiselect,
            session_state={},
        )
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=ParamKey("G1", "fc", "global", "", "F_min"),
                    label="F min",
                    kind="float",
                    default=0.0,
                    group="Grid",
                )
            ]
        )

        with patch("petromodeler.ui.widgets.parameter_form.st", fake_st):
            render_parameter_form(
                schema,
                {},
                _compute_derived,
                "G1",
                on_annotation_points_change=lambda indices: selected.extend(indices),
            )

        self.assertEqual(multiselect_calls[0][0], "在图上显示并标注的数据点")
        self.assertEqual(multiselect_calls[0][1]["options"], [])
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
