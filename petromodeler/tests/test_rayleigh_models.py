from __future__ import annotations

import unittest

import numpy as np

from petromodeler.application.services.parameter_resolver import ensure_defaults
from petromodeler.application.state.group_state import GroupState
from petromodeler.domain.common.types import ControlGrid, ControlVarType
from petromodeler.domain.models.degassing import DegassingModel
from petromodeler.domain.models.rayleigh import RayleighModel
from petromodeler.domain.models.registry import ModelRegistry
from petromodeler.domain.parameters.derived import fractionation_from_temperature
from petromodeler.domain.parameters.keys import ParamKey
from petromodeler.domain.quantities import ElementConc, IsotopeValue, quantity_id


class RayleighModelsTest(unittest.TestCase):
    group_id = "G1"

    def _key(self, model_id: str, role: str, quantity, name: str) -> str:
        return ParamKey(self.group_id, model_id, role, quantity_id(quantity), name).to_string()

    def test_devolatilization_keeps_original_element_and_delta_formulas(self) -> None:
        element = ElementConc("Sr")
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        params = {
            self._key("degassing", "initial", element, "Ci"): 100.0,
            self._key("degassing", "partition", element, "D"): 2.0,
            self._key("degassing", "initial", isotope, "delta_i"): 25.0,
            self._key("degassing", "global", isotope, "Delta"): 10.0,
        }
        result = DegassingModel().simulate(
            {element, isotope},
            self.group_id,
            params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
        )

        np.testing.assert_allclose(result.series_map[element], [100.0, 50.0])
        alpha = np.exp(10.0 / 1000.0)
        expected_delta = 25.0 + 1000.0 * (np.power([1.0, 0.5], alpha - 1.0) - 1.0)
        np.testing.assert_allclose(result.series_map[isotope], expected_delta)

    def test_rayleigh_returns_instantaneous_mineral_concentration(self) -> None:
        element = ElementConc("Sr")
        params = {
            self._key("rayleigh", "initial", element, "Ci"): 100.0,
            self._key("rayleigh", "partition", element, "D"): 2.0,
        }
        result = RayleighModel().simulate(
            {element},
            self.group_id,
            params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
        )

        np.testing.assert_allclose(result.series_map[element], [200.0, 100.0])

    def test_rayleigh_returns_instantaneous_mineral_isotope_value(self) -> None:
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        params = {
            self._key("rayleigh", "initial", isotope, "delta_i"): 25.0,
            self._key("rayleigh", "global", isotope, "Delta"): 10.0,
        }
        result = RayleighModel().simulate(
            {isotope},
            self.group_id,
            params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
        )

        alpha = np.exp(10.0 / 1000.0)
        expected = 1025.0 * np.power([1.0, 0.5], alpha - 1.0) * alpha - 1000.0
        np.testing.assert_allclose(result.series_map[isotope], expected)

    def test_zero_fractionation_preserves_delta_ratio_and_epsilon(self) -> None:
        quantities = {
            IsotopeValue("delta18O", "delta", carrier="O"): 25.0,
            IsotopeValue("87Sr/86Sr", "ratio", carrier="Sr"): 0.703,
            IsotopeValue("epsilonNd", "epsilon", carrier="Nd"): -5.0,
        }
        params = {}
        for q, initial in quantities.items():
            name = "delta_i" if q.kind == "delta" else "IC0"
            params[self._key("rayleigh", "initial", q, name)] = initial
            params[self._key("rayleigh", "global", q, "Delta")] = 0.0
        result = RayleighModel().simulate(
            set(quantities), self.group_id, params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5, 0.01])),
        )
        for q, initial in quantities.items():
            np.testing.assert_allclose(result.series_map[q], initial)

    def test_ratio_and_epsilon_fractionate_on_their_own_scales(self) -> None:
        ratio = IsotopeValue("87Sr/86Sr", "ratio", carrier="Sr")
        epsilon = IsotopeValue("epsilonNd", "epsilon", carrier="Nd")
        params = {}
        for q, initial in ((ratio, 0.703), (epsilon, -5.0)):
            params[self._key("rayleigh", "initial", q, "IC0")] = initial
            params[self._key("rayleigh", "global", q, "Delta")] = 10.0
        result = RayleighModel().simulate(
            {ratio, epsilon}, self.group_id, params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
        )
        alpha = np.exp(0.01)
        factor = alpha * np.power([1.0, 0.5], alpha - 1.0)
        np.testing.assert_allclose(result.series_map[ratio], 0.703 * factor)
        np.testing.assert_allclose(result.series_map[epsilon], 9995.0 * factor - 10000.0)

    def test_temperature_input_matches_direct_fractionation_for_both_models(self) -> None:
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        _, delta = fractionation_from_temperature(1.0, 2.0, 3.0, 873.15)
        grid = ControlGrid(ControlVarType.F, np.array([1.0, 0.5, 0.1]))
        for model in (DegassingModel(), RayleighModel()):
            params = {
                self._key(model.MODEL_ID, "initial", isotope, "delta_i"): 25.0,
                self._key(model.MODEL_ID, "global", isotope, "Delta"): delta,
            }
            direct = model.simulate({isotope}, self.group_id, params, grid)
            params.update({
                self._key(model.MODEL_ID, "global", isotope, "Delta_mode"): "From T-equation",
                self._key(model.MODEL_ID, "global", isotope, "A"): 1.0,
                self._key(model.MODEL_ID, "global", isotope, "B"): 2.0,
                self._key(model.MODEL_ID, "global", isotope, "C"): 3.0,
                self._key(model.MODEL_ID, "global", isotope, "T"): 600.0,
            })
            temperature = model.simulate({isotope}, self.group_id, params, grid)
            np.testing.assert_allclose(temperature.series_map[isotope], direct.series_map[isotope])

    def test_devolatilization_non_delta_isotopes_remain_constant(self) -> None:
        for q in (IsotopeValue("87Sr/86Sr", "ratio"), IsotopeValue("epsilonNd", "epsilon")):
            schema = DegassingModel().required_schema(self.group_id, {q})
            self.assertFalse(any(spec.key.name == "Delta_mode" for spec in schema.specs))
            params = {self._key("degassing", "initial", q, "IC0"): 0.703}
            result = DegassingModel().simulate(
                {q}, self.group_id, params,
                ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
            )
            np.testing.assert_allclose(result.series_map[q], 0.703)

    def test_rayleigh_excluded_element_is_zero_and_no_divergence_at_tiny_f(self) -> None:
        element = ElementConc("Sr")
        params = {
            self._key("rayleigh", "initial", element, "Ci"): 100.0,
            self._key("rayleigh", "partition", element, "D"): 0.0,
        }
        result = RayleighModel().simulate(
            {element}, self.group_id, params,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5, 1e-320])),
        )
        np.testing.assert_array_equal(result.series_map[element], [0.0, 0.0, 0.0])

    def test_models_have_separate_parameter_namespaces_and_phase_labels(self) -> None:
        element = ElementConc("Sr")
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        registry = ModelRegistry()
        for model in (DegassingModel(), RayleighModel()):
            registry.register(model)
            schema = model.required_schema(self.group_id, {element, isotope})
            self.assertTrue(all(spec.key.model_id == model.MODEL_ID for spec in schema.specs))
            self.assertTrue(all(spec.output_key.model_id == model.MODEL_ID for spec in schema.derived))
        self.assertEqual({spec.id for spec in registry.list_specs()}, {"degassing", "rayleigh"})
        rayleigh_schema = RayleighModel().required_schema(self.group_id, {element})
        partition = next(spec for spec in rayleigh_schema.specs if spec.key.name == "D")
        self.assertIn("矿物/熔体", partition.label)

    def test_legacy_project_group_migrates_parameters_and_keeps_original_results(self) -> None:
        element = ElementConc("Sr")
        isotope = IsotopeValue("delta18O", "delta", carrier="O")
        params = {
            self._key("rayleigh", "initial", element, "Ci"): 120.0,
            self._key("rayleigh", "partition", element, "D"): 2.0,
            self._key("rayleigh", "initial", isotope, "delta_i"): 25.0,
            self._key("rayleigh", "global", isotope, "Delta"): 10.0,
            ParamKey(self.group_id, "rayleigh", "global", "", "F_min").to_string(): 0.2,
        }
        snapshot = {"id": self.group_id, "model_id": "rayleigh", "params": params}
        group = GroupState.restore(snapshot)
        self.assertEqual(group.model_id, "degassing")
        self.assertEqual({ParamKey.from_string(k).model_id for k in group.params}, {"degassing"})
        self.assertEqual(
            group.params[ParamKey(self.group_id, "degassing", "global", "", "F_min").to_string()], 0.2
        )
        self.assertEqual(snapshot["model_id"], "rayleigh")
        model = DegassingModel()
        values = ensure_defaults(model.required_schema(self.group_id, {element, isotope}), group.params)
        result = model.simulate(
            {element, isotope}, self.group_id, values,
            ControlGrid(ControlVarType.F, np.array([1.0, 0.5])),
        )
        np.testing.assert_allclose(result.series_map[element], [120.0, 60.0])
        alpha = np.exp(0.01)
        np.testing.assert_allclose(
            result.series_map[isotope], 25.0 + 1000.0 * (np.power([1.0, 0.5], alpha - 1.0) - 1.0)
        )

    def test_new_project_retains_crystallization_rayleigh_group(self) -> None:
        snapshot = {"id": self.group_id, "model_id": "rayleigh", "params": {"legacy": 1.0}}
        group = GroupState.restore(snapshot, project_version=2)
        self.assertEqual(group.model_id, "rayleigh")
        self.assertEqual(group.params, {"legacy": 1.0})

    def test_legacy_non_rayleigh_group_is_unmodified(self) -> None:
        group = GroupState.restore({"id": self.group_id, "model_id": "fc", "params": {"legacy": 1.0}})
        self.assertEqual(group.model_id, "fc")
        self.assertEqual(group.params, {"legacy": 1.0})


if __name__ == "__main__":
    unittest.main()
