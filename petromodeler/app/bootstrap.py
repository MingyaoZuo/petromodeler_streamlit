"""Application bootstrap (dependency wiring).

Streamlit runs scripts top-to-bottom on every interaction, so we put all stateful
objects into `st.session_state`. The UI layer calls `build_container()` once.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..application.controllers.app_controller import AppController
from ..application.state.app_state import AppState
from ..application.services.simulation_service import SimulationService
from ..application.services.plot_service import PlotService
from ..application.services.import_service import ImportService
from ..application.services.export_service import ExportService
from ..application.services.normalization_service import NormalizationService
from ..application.services.derived_service import DerivedService
from ..application.services.project_service import ProjectService
from ..domain.models.registry import ModelRegistry

# Models
from ..domain.models.fc import FCModel
from ..domain.models.afc import AFCModel
from ..domain.models.fca import FCAModel
from ..domain.models.mm import MMModel
from ..domain.models.rayleigh import RayleighModel
from ..domain.models.degassing import DegassingModel
from ..domain.models.water_rock import WaterRockModel
from ..domain.models.mush_extract import MushExtractModel


@dataclass
class Container:
    state: AppState
    registry: ModelRegistry
    controller: AppController
    normalization: NormalizationService
    project: ProjectService


def build_registry() -> ModelRegistry:
    reg = ModelRegistry()
    reg.register(FCModel())
    reg.register(AFCModel())
    reg.register(FCAModel())
    reg.register(MMModel())
    reg.register(RayleighModel())
    reg.register(DegassingModel())
    reg.register(WaterRockModel())
    reg.register(MushExtractModel())
    return reg


def build_container(resources_dir: Path | None = None) -> Container:
    state = AppState()
    registry = build_registry()

    if resources_dir is None:
        resources_dir = Path(__file__).resolve().parents[1] / "resources"

    normalization_service = NormalizationService(resources_dir=resources_dir / "normalization")

    sim = SimulationService(model_registry=registry)
    plot = PlotService()
    importer = ImportService()
    exporter = ExportService()
    derived = DerivedService()
    project = ProjectService()

    controller = AppController(
        state=state,
        registry=registry,
        simulation_service=sim,
        plot_service=plot,
        import_service=importer,
        export_service=exporter,
        normalization_service=normalization_service,
        derived_service=derived,
    )

    return Container(
        state=state,
        registry=registry,
        controller=controller,
        normalization=normalization_service,
        project=project,
    )
