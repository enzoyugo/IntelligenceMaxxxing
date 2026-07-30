"""CMSR assessment ingestion use case (application layer)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from intelligence_maxxxing.application.errors import ApplicationError, IdempotencyConflictError
from intelligence_maxxxing.application.ports.trading_bridge import (
    TradingIdempotencyStorePort,
    TradingObservationStorePort,
)
from intelligence_maxxxing.domain_packs.trading.cmsr_policy_v1 import assess_cmsr_request
from intelligence_maxxxing.domain_packs.trading.cmsr_validate_v1 import (
    CMSR_ASSESSMENT_SCHEMA_VERSION,
    CMSR_POLICY_VERSION,
    content_hash,
    validate_cmsr_assessment,
    validate_cmsr_request,
)


class CmsrAssessmentError(ApplicationError):
    code = "CMSR_ASSESSMENT_ERROR"


class CmsrCausalityError(ApplicationError):
    code = "CAUSALITY_BLOCK"


class CmsrValidationError(ApplicationError):
    code = "CMSR_REQUEST_INVALID"


class CmsrAssessmentNotFoundError(ApplicationError):
    code = "CMSR_ASSESSMENT_NOT_FOUND"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


class TradingCmsrAssessmentService:
    def __init__(
        self,
        store: TradingObservationStorePort,
        idem_store: TradingIdempotencyStorePort,
    ) -> None:
        self.store = store
        self.idem_store = idem_store

    def get_assessment(self, assessment_id: str) -> dict[str, Any]:
        getter = getattr(self.store, "get_cmsr_assessment", None)
        if not callable(getter):
            raise CmsrAssessmentNotFoundError(f"cmsr assessment not found: {assessment_id}")
        row = getter(assessment_id)
        if not row:
            raise CmsrAssessmentNotFoundError(f"cmsr assessment not found: {assessment_id}")
        return row

    def assess(self, request: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise CmsrValidationError("request must be object")

        validation = validate_cmsr_request(request)
        if not validation["ok"]:
            if validation.get("causality_errors"):
                raise CmsrCausalityError(";".join(validation["errors"][:6]))
            raise CmsrValidationError(";".join(validation["errors"][:6]))

        idem = str(request.get("idempotency_key") or "")
        if not idem:
            raise CmsrValidationError("idempotency_key required")

        payload_hash = content_hash(request)
        created = _utc()

        claim = self.idem_store.claim_or_get(
            idempotency_key=idem,
            request_hash=payload_hash,
            created_at=created,
        )
        if claim.get("status") == "CONFLICT":
            raise IdempotencyConflictError(
                "idempotency key reused with a different cmsr request payload"
            )
        if claim.get("status") == "COMPLETE" and claim.get("response"):
            return claim["response"]
        if claim.get("status") == "PENDING":
            waited = self.idem_store.wait_complete(
                idempotency_key=idem, request_hash=payload_hash
            )
            if waited and waited.get("status") == "CONFLICT":
                raise IdempotencyConflictError(
                    "idempotency key reused with a different cmsr request payload"
                )
            if waited and waited.get("status") == "COMPLETE" and waited.get("response"):
                return waited["response"]
            raise CmsrAssessmentError("idempotency pending; retry shortly")

        try:
            req_id = request_id or str(request.get("request_id") or f"req_{uuid.uuid4().hex[:16]}")
            policy_out = assess_cmsr_request(request)
            assessment_id = "cmsr_asmt_" + hashlib.sha256(
                f"{payload_hash}|{request['setup_id']}|{idem}".encode()
            ).hexdigest()[:20]
            body = {
                "schema_version": CMSR_ASSESSMENT_SCHEMA_VERSION,
                "assessment_id": assessment_id,
                "request_id": req_id,
                "experiment_id": request.get("experiment_id"),
                "setup_id": request.get("setup_id"),
                "raw_setup_hash": request.get("raw_setup_hash"),
                "idempotency_key": idem,
                **policy_out,
                "created_at_utc": created,
                "input_hash": payload_hash,
            }
            body["output_hash"] = _hash({k: v for k, v in body.items() if k != "output_hash"})

            check = validate_cmsr_assessment(body)
            if not check["ok"]:
                raise CmsrAssessmentError(";".join(check["errors"][:6]))

            save_request = getattr(self.store, "save_cmsr_request", None)
            if callable(save_request):
                save_request(
                    {
                        "stored_at_utc": _utc(),
                        "request_id": req_id,
                        "idempotency_key": idem,
                        "payload_hash": payload_hash,
                        "request": request,
                    }
                )
            self.store.save_assessment(body)
            save_cmsr = getattr(self.store, "save_cmsr_assessment", None)
            if callable(save_cmsr):
                save_cmsr(body)
            self.store.save_idempotency(
                {
                    "idempotency_key": idem,
                    "payload_hash": payload_hash,
                    "assessment_id": assessment_id,
                    "created_at_utc": created,
                    "coordination": "sqlite_wal_v1",
                    "lane": "cmsr",
                }
            )
            self.idem_store.complete(
                idempotency_key=idem,
                request_hash=payload_hash,
                observation_id=None,
                assessment_id=assessment_id,
                policy_version=CMSR_POLICY_VERSION,
                response=body,
                response_hash=str(body["output_hash"]),
                completed_at=_utc(),
            )
            return body
        except Exception:
            self.idem_store.mark_failed(idempotency_key=idem, request_hash=payload_hash)
            raise
