"""Domain-layer exceptions.

All domain exceptions should inherit from DomainError so the application layer
can catch and present them consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class DomainError(Exception):
    """Base class for domain-layer errors."""


class ExpressionError(DomainError):
    pass


class ModelComputationError(DomainError):
    pass


@dataclass
class ParameterValidationError(DomainError):
    """Represents a validation issue for a single parameter key."""

    key: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"{self.key}: {self.message}"
