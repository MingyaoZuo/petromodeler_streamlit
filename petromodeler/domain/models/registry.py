"""Model registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .base import IModel, ModelSpec


class ModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, IModel] = {}

    def register(self, model: IModel) -> None:
        spec = model.spec()
        self._models[spec.id] = model

    def get(self, model_id: str) -> IModel:
        if model_id not in self._models:
            raise KeyError(f"Model not registered: {model_id}")
        return self._models[model_id]

    def list_specs(self) -> List[ModelSpec]:
        return [m.spec() for m in self._models.values()]

    def has(self, model_id: str) -> bool:
        return model_id in self._models
