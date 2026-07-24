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
from intelligence_maxxxing.infrastructure.trading.sqlite_idempotency_store import (
    TradingSqliteIdempotencyStore,
)


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
    def __init__(
        self,
        store: TradingJsonlStore | None = None,
        idem_store: TradingSqliteIdempotencyStore | None = None,
    ) -> None:
        self.store = store or TradingJsonlStore()
        self.idem_store = idem_store or TradingSqliteIdempotencyStore(
            path=(self.store.root / "trading_idempotency_v1.sqlite3")
        )

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
            "storage": {
                "backend": "sqlite_wal+jsonl_mirror",
                "path": str(self.store.root),
                "idempotency_db": str(self.idem_store.path),
                **counts,
            },
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
        created = _utc()

        claim = self.idem_store.claim_or_get(
            idempotency_key=idem,
            request_hash=payload_hash,
            created_at=created,
        )
        if claim.get("status") == "CONFLICT":
            raise IdempotencyConflictError(
                "idempotency key reused with a different observation payload"
            )
        if claim.get("status") == "COMPLETE" and claim.get("response"):
            return claim["response"]
        if claim.get("status") == "PENDING":
            waited = self.idem_store.wait_complete(
                idempotency_key=idem, request_hash=payload_hash
            )
            if waited and waited.get("status") == "CONFLICT":
                raise IdempotencyConflictError(
                    "idempotency key reused with a different observation payload"
                )
            if waited and waited.get("status") == "COMPLETE" and waited.get("response"):
                return waited["response"]
            # Peer stalled — do not create a second assessment.
            raise TradingAssessmentError("idempotency pending; retry shortly")

        # We uniquely claimed PENDING — generate exactly one assessment.
        try:
            obs_id = str(observation.get("observation_id") or f"OBS_{uuid.uuid4().hex[:20]}")
            observation = {**observation, "observation_id": obs_id}
            self.store.save_observation(
                {
                    "stored_at_utc": _utc(),
                    "observation_id": obs_id,
                    "idempotency_key": idem,
                    "payload_hash": payload_hash,
                    "observation": observation,
                }
            )

            policy_out = assess_observation(observation)
            req = request_id or f"req_{uuid.uuid4().hex[:16]}"
            assessment_id = f"ASM_{uuid.uuid4().hex[:20]}"
            setup = observation.get("economic_setup") or {}
            body = {
                "schema_version": "im.tmx.assessment.v1",
                "assessment_id": assessment_id,
                "request_id": req,
                "experiment_id": observation.get("experiment_id"),
                "economic_setup_id": setup.get("economic_setup_id"),
                "observation_id": obs_id,
                "idempotency_key": idem,
                **policy_out,
                "created_at_utc": created,
                "input_hash": payload_hash,
            }
            body["output_hash"] = _hash({k: v for k, v in body.items() if k != "output_hash"})
            self.store.save_assessment(body)
            # JSONL mirror of idempotency (non-authoritative).
            self.store.save_idempotency(
                {
                    "idempotency_key": idem,
                    "payload_hash": payload_hash,
                    "assessment_id": assessment_id,
                    "created_at_utc": created,
                    "coordination": "sqlite_wal_v1",
                }
            )
            self.idem_store.complete(
                idempotency_key=idem,
                request_hash=payload_hash,
                observation_id=obs_id,
                assessment_id=assessment_id,
                policy_version=POLICY_VERSION,
                response=body,
                response_hash=str(body["output_hash"]),
                completed_at=_utc(),
            )
            return body
        except Exception:
            self.idem_store.mark_failed(idempotency_key=idem, request_hash=payload_hash)
            raise
