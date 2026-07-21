"""Trading assessment ingestion use case (application layer)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from intelligence_maxxxing.application.errors import ApplicationError, IdempotencyConflictError
from intelligence_maxxxing.domain_packs.trading.policy_v1 import (
    POLICY_FROZEN_AT,
    POLICY_ID,
    POLICY_VERSION,
    RULESET_HASH,
    assess_observation,
)
from intelligence_maxxxing.infrastructure.trading.jsonl_store import TradingJsonlStore


class TradingAssessmentError(ApplicationError):
    code = "TRADING_ASSESSMENT_ERROR"


class TradingAssessmentNotFoundError(ApplicationError):
    code = "ASSESSMENT_NOT_FOUND"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


class TradingAssessmentService:
    def __init__(self, store: TradingJsonlStore | None = None) -> None:
        self.store = store or TradingJsonlStore()

    def active_policy(self) -> dict[str, Any]:
        return {
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "frozen_at_utc": POLICY_FROZEN_AT,
            "ruleset_hash": RULESET_HASH,
            "model_version": None,
            "research_only": True,
        }

    def health(self) -> dict[str, Any]:
        counts = self.store.counts()
        return {
            "status": "ok",
            "service": "trading_assessment",
            "policy": self.active_policy(),
            "storage": {"backend": "jsonl", "path": str(self.store.root), **counts},
            "ollama": {"status": "DISABLED", "role": "explain_only_optional"},
            "research_only": True,
        }

    def get_assessment(self, assessment_id: str) -> dict[str, Any]:
        row = self.store.get_assessment(assessment_id)
        if not row:
            raise TradingAssessmentNotFoundError(f"assessment not found: {assessment_id}")
        return row

    def assess(self, observation: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
        if not isinstance(observation, dict):
            raise TradingAssessmentError("observation must be object")
        idem = str(observation.get("idempotency_key") or "")
        if not idem:
            raise TradingAssessmentError("idempotency_key required")
        payload_hash = _hash(observation)
        existing = self.store.find_idempotency(idem)
        if existing:
            if existing.get("payload_hash") != payload_hash:
                raise IdempotencyConflictError(
                    "idempotency key reused with a different observation payload"
                )
            cached = self.store.get_assessment(str(existing.get("assessment_id")))
            if cached:
                return cached

        self.store.save_observation(
            {
                "stored_at_utc": _utc(),
                "observation_id": observation.get("observation_id"),
                "idempotency_key": idem,
                "payload_hash": payload_hash,
                "observation": observation,
            }
        )

        policy_out = assess_observation(observation)
        created = _utc()
        req = request_id or f"req_{uuid.uuid4().hex[:16]}"
        assessment_id = f"ASM_{uuid.uuid4().hex[:20]}"
        setup = observation.get("economic_setup") or {}
        body = {
            "schema_version": "im.tmx.assessment.v1",
            "assessment_id": assessment_id,
            "request_id": req,
            "experiment_id": observation.get("experiment_id"),
            "economic_setup_id": setup.get("economic_setup_id"),
            "observation_id": observation.get("observation_id"),
            "idempotency_key": idem,
            **policy_out,
            "created_at_utc": created,
            "input_hash": payload_hash,
        }
        body["output_hash"] = _hash({k: v for k, v in body.items() if k != "output_hash"})
        self.store.save_assessment(body)
        self.store.save_idempotency(
            {
                "idempotency_key": idem,
                "payload_hash": payload_hash,
                "assessment_id": assessment_id,
                "created_at_utc": created,
            }
        )
        return body
