"""Small helpers for model implementations.

Models receive parameters as a dict keyed by ParamKey.to_string().
These helpers make it easy to construct keys consistently.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..parameters.keys import ParamKey


def make_key(group_id: str, model_id: str, role: str, quantity_id: str, name: str) -> str:
    return ParamKey(group_id, model_id, role, quantity_id, name).to_string()


def get_required(params: Dict[str, Any], key_str: str) -> Any:
    if key_str not in params:
        raise KeyError(f"Missing required parameter: {key_str}")
    return params[key_str]


def get_float(params: Dict[str, Any], key_str: str, default: Optional[float] = None) -> float:
    if key_str not in params:
        if default is None:
            raise KeyError(f"Missing required parameter: {key_str}")
        return float(default)
    return float(params[key_str])


def get_int(params: Dict[str, Any], key_str: str, default: Optional[int] = None) -> int:
    if key_str not in params:
        if default is None:
            raise KeyError(f"Missing required parameter: {key_str}")
        return int(default)
    return int(params[key_str])


def get_bool(params: Dict[str, Any], key_str: str, default: bool = False) -> bool:
    if key_str not in params:
        return bool(default)
    return bool(params[key_str])
