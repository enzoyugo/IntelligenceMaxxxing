"""Public Python client for the IntelligenceMaxxxing Engine.

This package consumes the public HTTP API only. It never imports the Engine
Core (`intelligence_maxxxing`); that boundary is protected by import-linter
and constitutional tests.
"""

from intelligence_maxxxing_client.client import (
    IntelligenceMaxxxingClient,
    new_idempotency_key,
)
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
    BeliefListView,
    BeliefView,
    EnvelopeMeta,
    EvaluateExperimentResult,
    ExperimentProgressView,
    ExperimentView,
    HealthView,
    HypothesisListView,
    HypothesisParameters,
    HypothesisView,
    HypothesisWriteResult,
    LearningListView,
    LearningView,
    ObservationAcceptedView,
    ObservationListView,
    ObservationView,
)

__all__ = [
    "AuditView",
    "BeliefListView",
    "BeliefView",
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
    "EvaluateExperimentResult",
    "ExperimentProgressView",
    "ExperimentView",
    "HealthView",
    "HypothesisListView",
    "HypothesisParameters",
    "HypothesisView",
    "HypothesisWriteResult",
    "IntelligenceMaxxxingClient",
    "LearningListView",
    "LearningView",
    "ObservationAcceptedView",
    "ObservationListView",
    "ObservationView",
    "new_idempotency_key",
]
