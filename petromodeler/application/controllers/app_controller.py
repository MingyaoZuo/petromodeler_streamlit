"""Application controller.

The Streamlit UI calls into this controller to mutate state or run computations.
This keeps UI modules mostly presentation-only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from ...domain.models.base import ModelSpec
from ...domain.models.registry import ModelRegistry
from ...domain.parameters.keys import ParamKey
from ...domain.parameters.specs import DerivedSpec, ParameterSchema
from ..state.app_state import AppState
from ..state.group_state import GroupState
from ..state.axis_state import AxisState
from ..state.dataset_state import DatasetState
from ..services.simulation_service import SimulationService, ValidationReport
from ..services.plot_service import PlotService
from ..services.import_service import ImportService
from ..services.export_service import ExportService
from ..services.normalization_service import NormalizationService
from ..services.derived_service import DerivedService
from ..services.parameter_resolver import ensure_defaults, resolve_schema


@dataclass(frozen=True)
class GroupParameterForm:
    schema: ParameterSchema
    values: Dict[str, Any]
    validation_report: ValidationReport
    annotation_detail_table: Optional[pd.DataFrame]


class AppController:
    def __init__(
        self,
        state: AppState,
        registry: ModelRegistry,
        simulation_service: SimulationService,
        plot_service: PlotService,
        import_service: ImportService,
        export_service: ExportService,
        normalization_service: NormalizationService,
        derived_service: DerivedService,
    ) -> None:
        self.state = state
        self.registry = registry
        self.sim = simulation_service
        self.plot = plot_service
        self.importer = import_service
        self.exporter = export_service
        self.norm = normalization_service
        self.derived = derived_service

    # ---- Models ----
    def list_model_specs(self) -> list[ModelSpec]:
        return self.registry.list_specs()

    def model_labels(self) -> dict[str, str]:
        return {spec.name: spec.id for spec in self.list_model_specs()}

    def model_spec(self, model_id: str) -> ModelSpec:
        return self.registry.get(model_id).spec()

    def model_short_name(self, model_id: str) -> str:
        try:
            return self.model_spec(model_id).name.split("(", 1)[0].strip()
        except Exception:
            return model_id

    # ---- Axis ----
    def set_axis(self, axis: AxisState) -> None:
        self.state.axis = axis
        self.clear_results()

    def replace_state(self, state: AppState, preserve_dataset: bool = True) -> None:
        current_dataset = self.state.dataset
        if preserve_dataset and state.dataset.df is None and current_dataset.df is not None:
            state.dataset = DatasetState(
                df=current_dataset.df,
                x_col=current_dataset.x_col,
                y_col=current_dataset.y_col,
                group_col=current_dataset.group_col,
                selected_group_values=(
                    list(current_dataset.selected_group_values)
                    if current_dataset.selected_group_values is not None
                    else None
                ),
            )

        self.state = state
        self._drop_missing_dataset_mapping()

    # ---- Groups ----
    def get_next_group_name(self) -> str:
        existing_names = {g.name for g in self.state.groups}
        index = 1
        while f"Group{index}" in existing_names:
            index += 1
        return f"Group{index}"

    def _ensure_unique_group_name(self, name: str, *, exclude_group_id: str | None = None) -> None:
        for group in self.state.groups:
            if group.group_id != exclude_group_id and group.name == name:
                raise ValueError(f"Group name already exists: {name}")

    def add_group(self, name: str, model_id: str) -> GroupState:
        name = name.strip() or self.get_next_group_name()
        self._ensure_unique_group_name(name)
        self.clear_results()
        gid = f"G{len(self.state.groups)+1}_{uuid.uuid4().hex[:6]}"
        g = GroupState(group_id=gid, name=name, model_id=model_id)
        self.state.groups.append(g)
        return g

    def delete_group(self, group_id: str) -> None:
        self.state.groups = [g for g in self.state.groups if g.group_id != group_id]

    def move_group(self, group_id: str, offset: int) -> None:
        if offset == 0:
            return

        current_index = next((i for i, g in enumerate(self.state.groups) if g.group_id == group_id), None)
        if current_index is None:
            return

        target_index = current_index + offset
        if target_index < 0 or target_index >= len(self.state.groups):
            return

        group = self.state.groups.pop(current_index)
        self.state.groups.insert(target_index, group)

    def update_group_model(self, group_id: str, model_id: str) -> None:
        g = self.state.get_group(group_id)
        if not g:
            return
        if g.model_id != model_id:
            g.model_id = model_id
            g.params = {}
            g.clear_result()

    def set_group_visible(self, group_id: str, visible: bool) -> None:
        g = self.state.get_group(group_id)
        if g:
            g.visible = bool(visible)

    def set_group_name(self, group_id: str, name: str) -> None:
        g = self.state.get_group(group_id)
        if g:
            name = name.strip()
            self._ensure_unique_group_name(name, exclude_group_id=group_id)
            g.name = name

    def set_group_params(self, group_id: str, params: Dict[str, Any]) -> None:
        g = self.state.get_group(group_id)
        if not g:
            return
<<<<<<<<< Temporary merge branch 1
        g.params = dict(params)
        g.clear_result()
=========
        new_params = dict(params)
        if new_params != g.params:
            g.clear_result()
        g.params = new_params

    def clone_group_params(self, source_group_id: str, target_group_id: str) -> None:
        source = self.state.get_group(source_group_id)
        target = self.state.get_group(target_group_id)
        if not source or not target:
            return

        cloned: Dict[str, Any] = {}
        for key_str, value in source.params.items():
            try:
                key = ParamKey.from_string(key_str)
            except ValueError as exc:
                raise ValueError(f"Cannot clone malformed parameter key: {key_str}") from exc
            if key.group_id != source_group_id:
                raise ValueError(
                    f"Cannot clone parameter for group {key.group_id!r} from {source_group_id!r}"
                )
            cloned[key.with_group_id(target_group_id).to_string()] = value

        target.params = cloned
        target.clear_result()

    def group_parameter_form(self, group_id: str) -> Optional[GroupParameterForm]:
        group = self.state.get_group(group_id)
        if group is None:
            return None

        model = self.registry.get(group.model_id)
        schema = resolve_schema(model, group.group_id, self.state.axis.x_expr, self.state.axis.y_expr)
        values = ensure_defaults(schema, group.params)
        report, _, _ = self.sim.validate_group(group, self.state.axis)
        return GroupParameterForm(
            schema=schema,
            values=values,
            validation_report=report,
            annotation_detail_table=self._annotation_detail_table(group, values),
        )

    def _annotation_detail_table(self, group: GroupState, values: Dict[str, Any]) -> Optional[pd.DataFrame]:
        if group.last_result and group.last_result.detail_table is not None:
            return group.last_result.detail_table

        preview_group = GroupState(
            group_id=group.group_id,
            name=group.name,
            model_id=group.model_id,
            params=values,
            visible=group.visible,
        )
        try:
            model = self.registry.get(group.model_id)
            grid = self.sim.build_grid(model, preview_group)
        except Exception:
            return None
        return pd.DataFrame({grid.var.value: grid.values})

    # ---- Plot ----
    def set_plot_title(self, title: str) -> None:
        self.state.plot.title = title

    def set_plot_show_dataset(self, show_dataset: bool) -> None:
        self.state.plot.show_dataset = bool(show_dataset)

    def set_plot_show_legend(self, show_legend: bool) -> None:
        self.state.plot.show_legend = bool(show_legend)

    def set_group_annotation_points(self, group_id: str, indices: list[int]) -> None:
        if self.state.get_group(group_id) is None:
            return
        self.state.plot.annotated_points_by_group[group_id] = [int(i) for i in indices]

    def detail_tables_for_export(self):
        for group in self.state.groups:
            if not group.visible or not group.last_result or group.last_result.detail_table is None:
                continue
            yield group.name, self.model_short_name(group.model_id), group.last_result.detail_table

    def export_detail_table_excel(self, df: pd.DataFrame) -> bytes:
        return self.exporter.dataframe_to_excel_bytes(df)

    def export_grouped_detail_tables_excel(self, grouped_tables) -> bytes:
        return self.exporter.grouped_dataframes_to_single_sheet_excel_bytes(grouped_tables)

    # ---- Dataset ----
    def load_dataset_excel(self, file_obj) -> pd.DataFrame:
        df = self.importer.load_excel(file_obj)
        self.state.dataset.df = df
        self._drop_missing_dataset_mapping()
        return df

    def infer_numeric_columns(self, df: pd.DataFrame) -> list[str]:
        return self.importer.infer_numeric_columns(df)

    def set_dataset_mapping(
        self,
        x_col: Optional[str],
        y_col: Optional[str],
        group_col: Optional[str],
        selected_group_values: Optional[list[str]] = None,
    ) -> None:
        self.state.dataset.x_col = x_col
        self.state.dataset.y_col = y_col
        self.state.dataset.group_col = group_col
        self.state.dataset.selected_group_values = (
            [str(value) for value in selected_group_values]
            if group_col and selected_group_values is not None
            else None
        )
        self._drop_missing_dataset_mapping()

    def _drop_missing_dataset_mapping(self) -> None:
        df = self.state.dataset.df
        if df is None:
            return

        columns = set(str(c) for c in df.columns)
        if self.state.dataset.x_col not in columns:
            self.state.dataset.x_col = None
        if self.state.dataset.y_col not in columns:
            self.state.dataset.y_col = None
        if self.state.dataset.group_col not in columns:
            self.state.dataset.group_col = None
            self.state.dataset.selected_group_values = None
            return

        selected_group_values = self.state.dataset.selected_group_values
        if selected_group_values is None:
            return

        available_values = {
            str(value)
            for value in df[self.state.dataset.group_col].dropna().unique()
        }
        self.state.dataset.selected_group_values = [
            value for value in selected_group_values if value in available_values
        ]

    # ---- Resource-backed helpers ----
    def available_normalization_sources(self) -> list[str]:
        return self.norm.available_sources()

    def load_normalization_values(self, source: str) -> dict[str, float]:
        return self.norm.load(source)

    def compute_derived_parameter(self, spec: DerivedSpec, values: Dict[str, Any]) -> Optional[float]:
        return self.derived.compute(spec, values)

    # ---- Simulation / Plot ----
    def clear_results(self, group_id: Optional[str] = None) -> None:
        if group_id is not None:
            group = self.state.get_group(group_id)
            if group:
                group.clear_result()
            return

        for group in self.state.groups:
            group.clear_result()

    def current_results(self):
        return {
            group.group_id: group.last_result
            for group in self.state.groups
            if group.visible and group.last_result is not None
        }

    def run_group(self, group_id: str):
        g = self.state.get_group(group_id)
        if not g:
            return None
        try:
            res = self.sim.run_group(g, self.state.axis)
            g.last_result = res
            g.last_error = None
            return res
        except Exception as e:
            g.last_result = None
            g.last_error = str(e)
            return None

    def run_all(self):
        results = {}
        for g in self.state.groups:
            if not g.visible:
                continue
            r = self.run_group(g.group_id)
            if r is not None:
                results[g.group_id] = r
        return results

    def build_plot(self, results_by_group):
        return self.plot.build_figure(
            results_by_group=results_by_group,
            groups=self.state.groups,
            axis=self.state.axis,
            dataset=self.state.dataset,
            plot_state=self.state.plot,
        )
