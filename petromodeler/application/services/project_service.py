"""Project save/load application service."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ...infrastructure.persistence.project_store import ProjectStore
from ..state.app_state import AppState


class ProjectService:
    def __init__(self, store: ProjectStore | None = None) -> None:
        self._store = store or ProjectStore()

    @property
    def default_filename(self) -> str:
        return self._store.DEFAULT_FILENAME

    def default_save_path(self, base_dir: Path | None = None) -> Path:
        return (base_dir or Path.cwd()) / self.default_filename

    def dumps(self, state: AppState) -> str:
        return self._store.dumps(state)

    def loads(self, text: str) -> AppState:
        return self._store.loads(text)

    def payload_digest(self, payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def save_text(self, project_json: str, path: str | Path) -> Path:
        return self._store.save_text(project_json, path)

    def save(self, state: AppState, path: str | Path) -> Path:
        return self._store.save(state, path)
