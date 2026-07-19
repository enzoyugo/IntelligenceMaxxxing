"""Public Python client for the IntelligenceMaxxxing Engine.

This package consumes the public HTTP API only. It never imports the Engine
Core (`intelligence_maxxxing`); that boundary is protected by import-linter
and constitutional tests.
"""

from intelligence_maxxxing_client.client import IntelligenceMaxxxingClient
from intelligence_maxxxing_client.errors import (
    EngineAPIError,
    EngineClientError,
    EngineConflictError,
    EngineForbiddenError,
    EngineNotFoundError,
    EngineServiceUnavailableError,
    EngineUnauthorizedError,
    EngineUnavailableError,
    EngineValidationError,
)
from intelligence_maxxxing_client.models import (
    AuditView,
    EnvelopeMeta,
    HealthView,
    ObservationAcceptedView,
    ObservationListView,
    ObservationView,
)

__all__ = [
    "AuditView",
    "EngineAPIError",
    "EngineClientError",
    "EngineConflictError",
    "EngineForbiddenError",
    "EngineNotFoundError",
    "EngineServiceUnavailableError",
    "EngineUnauthorizedError",
    "EngineUnavailableError",
    "EngineValidationError",
    "EnvelopeMeta",
    "HealthView",
    "IntelligenceMaxxxingClient",
    "ObservationAcceptedView",
    "ObservationListView",
    "ObservationView",
]
