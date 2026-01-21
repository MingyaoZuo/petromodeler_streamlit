"""Application controller.

The Streamlit UI calls into this controller to mutate state or run computations.
This keeps UI modules mostly presentation-only.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import pandas as pd

from ...domain.models.registry import ModelRegistry
from ..state.app_state import AppState
from ..state.group_state import GroupState
from ..state.axis_state import AxisState
from ..services.simulation_service import SimulationService
from ..services.plot_service import PlotService
from ..services.import_service import ImportService
from ..services.export_service import ExportService
from ..services.normalization_service import NormalizationService
from ..services.derived_service import DerivedService


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

    # ---- Axis ----
    def set_axis(self, axis: AxisState) -> None:
        self.state.axis = axis
        # changing axis invalidates cached results
        for g in self.state.groups:
            g.clear_result()

    # ---- Groups ----
    def add_group(self, name: str, model_id: str) -> GroupState:
        gid = f"G{len(self.state.groups)+1}_{uuid.uuid4().hex[:6]}"
        g = GroupState(group_id=gid, name=name or gid, model_id=model_id)
        self.state.groups.append(g)
        return g

    def delete_group(self, group_id: str) -> None:
        self.state.groups = [g for g in self.state.groups if g.group_id != group_id]

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
            g.name = name

    def set_group_params(self, group_id: str, params: Dict[str, Any]) -> None:
        g = self.state.get_group(group_id)
        if not g:
            return
        g.params = dict(params)
        g.clear_result()

    # ---- Dataset ----
    def load_dataset_excel(self, file_obj) -> pd.DataFrame:
        df = self.importer.load_excel(file_obj)
        self.state.dataset.df = df
        return df

    def set_dataset_mapping(self, x_col: Optional[str], y_col: Optional[str], group_col: Optional[str]) -> None:
        self.state.dataset.x_col = x_col
        self.state.dataset.y_col = y_col
        self.state.dataset.group_col = group_col

    # ---- Simulation / Plot ----
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
