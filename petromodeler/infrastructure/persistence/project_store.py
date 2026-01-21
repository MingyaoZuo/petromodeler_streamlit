"""Project save/load.

In Streamlit, files are typically downloaded/uploaded by the user.
This module provides JSON (de)serialization helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ...application.state.app_state import AppState


class ProjectStore:
    def dumps(self, state: AppState) -> str:
        return json.dumps(state.snapshot(), ensure_ascii=False, indent=2)

    def loads(self, text: str) -> AppState:
        data = json.loads(text)
        return AppState.restore(data)
