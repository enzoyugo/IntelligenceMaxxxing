"""Ports for TMX↔IM trading bridge storage (application-layer contracts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class TradingObservationStorePort(Protocol):
    root: Path

    def counts(self) -> dict[str, Any]: ...

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None: ...

    def save_observation(self, row: dict[str, Any]) -> None: ...

    def save_assessment(self, row: dict[str, Any]) -> None: ...

    def save_idempotency(self, row: dict[str, Any]) -> None: ...


class TradingIdempotencyStorePort(Protocol):
    path: Path

    def claim_or_get(
        self, *, idempotency_key: str, request_hash: str, created_at: str
    ) -> dict[str, Any]: ...

    def wait_complete(
        self, *, idempotency_key: str, request_hash: str
    ) -> dict[str, Any] | None: ...

    def complete(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        observation_id: str,
        assessment_id: str,
        policy_version: str,
        response: dict[str, Any],
        response_hash: str,
        completed_at: str,
    ) -> None: ...

    def mark_failed(self, *, idempotency_key: str, request_hash: str) -> None: ...
