"""Normalization tables service.

Provides built-in normalization values used by Eu/Ce anomalies.

The built-in tables are stored under `petromodeler/resources/normalization/`.
Users can also specify custom values in the UI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping


class NormalizationService:
    def __init__(self, resources_dir: Path) -> None:
        self._dir = resources_dir
        self._cache: Dict[str, Dict[str, float]] = {}

    def load(self, source: str) -> Dict[str, float]:
        if source == "custom":
            return {}
        if source in self._cache:
            return dict(self._cache[source])
        f = self._dir / f"{source}.json"
        if not f.exists():
            raise FileNotFoundError(f"Normalization table not found: {f}")
        data = json.loads(f.read_text(encoding="utf-8"))
        # ensure floats
        table = {str(k): float(v) for k, v in data.items()}
        self._cache[source] = table
        return dict(table)

    def available_sources(self) -> list[str]:
        return ["chondrite", "nasc", "primitive_mantle", "custom"]
