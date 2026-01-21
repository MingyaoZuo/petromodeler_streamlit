from __future__ import annotations

import unittest

from petromodeler.application.services.parameter_resolver import ensure_defaults, resolve_requested_quantities
from petromodeler.domain.expressions import BinaryOp, Leaf, expression_from_dict
from petromodeler.domain.models.afc import AFCModel
from petromodeler.domain.models.fc import FCModel
from petromodeler.domain.models.fca import FCAModel
from petromodeler.domain.models.mm import MMModel
from petromodeler.domain.models.mush_extract import MushExtractModel
from petromodeler.domain.models.rayleigh import RayleighModel
from petromodeler.domain.models.water_rock import WaterRockModel
from petromodeler.domain.parameters.derived import compute_derived, fractionation_from_temperature
from petromodeler.domain.parameters.keys import ParamKey
from petromodeler.domain.parameters.specs import ParameterSchema, ParameterSpec
from petromodeler.domain.quantities import ElementConc, IsotopeValue


class ExpressionAndResolverTest(unittest.TestCase):
    def test_expression_round_trip(self) -> None:
        expr = BinaryOp(
            op="+",
            left=Leaf(ElementConc("Sr")),
            right=Leaf(ElementConc("Nd")),
        )

        restored = expression_from_dict(expr.to_dict())

        self.assertEqual(restored.label(), expr.label())
        self.assertEqual(restored.to_dict(), expr.to_dict())

    def test_resolve_requested_quantities_collects_dependencies(self) -> None:
        x_expr = BinaryOp("+", Leaf(ElementConc("Sr")), Leaf(ElementConc("Nd")))
        y_expr = Leaf(ElementConc("Sr"))

        deps = resolve_requested_quantities(x_expr, y_expr)

        self.assertEqual({q.element for q in deps}, {"Sr", "Nd"})

    def test_ensure_defaults_fills_missing_values(self) -> None:
        schema = ParameterSchema(
            specs=[
                ParameterSpec(
                    key=ParamKey("G1", "fc", "global", "", "F_min"),
                    label="F_min",
                    default=0.05,
                ),
                ParameterSpec(
                    key=ParamKey("G1", "fc", "global", "", "n_points"),
                    label="n_points",
                    default=50,
                    kind="int",
                ),
            ]
        )

        values = ensure_defaults(schema, {schema.specs[0].key.to_string(): 0.1})

        self.assertEqual(values[schema.specs[0].key.to_string()], 0.1)
        self.assertEqual(values[schema.specs[1].key.to_string()], 50)

    def test_temperature_equation_treats_T_as_celsius(self) -> None:
        expected = fractionation_from_temperature(1.0, 2.0, 3.0, 873.15)[1]

        actual = compute_derived(
            "fractionation_from_temperature:Delta",
            {"A": 1.0, "B": 2.0, "C": 3.0, "T": 600.0},
        )

        self.assertAlmostEqual(actual, expected)

    def test_temperature_equation_schema_uses_celsius_step(self) -> None:
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        for model in (RayleighModel(), AFCModel(), WaterRockModel()):
            schema = model.required_schema("G1", {isotope})
            temp_specs = [spec for spec in schema.specs if spec.key.name == "T"]

            self.assertTrue(temp_specs)
            self.assertEqual(temp_specs[0].default, 600.0)
            self.assertEqual(temp_specs[0].step, 10.0)
            self.assertIn("°C", temp_specs[0].label)

    def test_element_concentration_schema_uses_step_10(self) -> None:
        quantity = ElementConc("Sr")
        concentration_names = {"C0", "Ca", "Ci", "C", "Cr_i", "Cw_i"}
        for model in (FCModel(), FCAModel(), MMModel(), MushExtractModel(), RayleighModel(), AFCModel(), WaterRockModel()):
            schema = model.required_schema("G1", {quantity})
            concentration_specs = [spec for spec in schema.specs if spec.key.name in concentration_names]

            self.assertTrue(concentration_specs)
            for spec in concentration_specs:
                self.assertEqual(spec.step, 10.0)

    def test_isotope_numeric_schema_uses_step_0_1(self) -> None:
        isotope = IsotopeValue("delta11B", "delta", carrier="B")
        isotope_names = {
            "IC0",
            "ICa",
            "IC",
            "IC_melt",
            "Delta",
            "delta_i",
            "delta0",
            "deltaa",
            "delta_r_i",
            "delta_w_i",
            "A",
            "B",
            "C",
        }
        for model in (FCModel(), FCAModel(), MMModel(), MushExtractModel(), RayleighModel(), AFCModel(), WaterRockModel()):
            schema = model.required_schema("G1", {isotope})
            isotope_specs = [
                spec
                for spec in schema.specs
                if spec.key.name in isotope_names
                and (spec.key.quantity_id.startswith("iso:") or spec.group == "Isotope params")
            ]

            self.assertTrue(isotope_specs)
            for spec in isotope_specs:
                self.assertEqual(spec.step, 0.1)

    def test_control_grid_schema_allows_points_or_step(self) -> None:
        quantity = ElementConc("Sr")
        expected_step_defaults = {
            "fc": 0.01,
            "fca": 0.01,
            "mm": 0.01,
            "mush_extract": 0.01,
            "rayleigh": 0.01,
            "afc": 0.01,
            "water_rock": 0.1,
        }
        for model in (FCModel(), FCAModel(), MMModel(), MushExtractModel(), RayleighModel(), AFCModel(), WaterRockModel()):
            schema = model.required_schema("G1", {quantity})
            by_name = {spec.key.name: spec for spec in schema.specs}

            self.assertEqual(by_name["grid_mode"].choices, ["By points", "By step"])
            self.assertEqual(by_name["grid_mode"].default, "By points")
            self.assertEqual(by_name["n_points"].visible_if, (by_name["grid_mode"].key.to_string(), ["By points"]))
            self.assertEqual(by_name["grid_step"].visible_if, (by_name["grid_mode"].key.to_string(), ["By step"]))
            self.assertEqual(by_name["grid_step"].default, expected_step_defaults[model.MODEL_ID])


if __name__ == "__main__":
    unittest.main()
