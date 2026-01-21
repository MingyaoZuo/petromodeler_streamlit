"""Project save/load.

In Streamlit, files are typically downloaded/uploaded by the user.
This module provides JSON (de)serialization helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...application.state.app_state import AppState


class ProjectStore:
    DEFAULT_FILENAME = "petromodeler_project.json"

    def dumps(self, state: AppState) -> str:
        return json.dumps(state.snapshot(), ensure_ascii=False, indent=2)

    def loads(self, text: str) -> AppState:
        data = json.loads(text)
        return AppState.restore(data)

    def resolve_save_path(self, path: str | Path) -> Path:
        resolved = Path(path).expanduser()
        if resolved.exists() and resolved.is_dir():
            return resolved / self.DEFAULT_FILENAME
        if resolved.suffix.lower() != ".json":
            return resolved.with_suffix(".json")
        return resolved

    def save_text(self, text: str, path: str | Path) -> Path:
        resolved = self.resolve_save_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text, encoding="utf-8")
        return resolved

    def save(self, state: AppState, path: str | Path) -> Path:
        return self.save_text(self.dumps(state), path)
