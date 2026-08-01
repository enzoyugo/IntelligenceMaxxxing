"""Generic multi-strategy assessment ingestion use case (application layer)."""

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
from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    content_hash,
    validate_strategy_assessment,
    validate_strategy_request,
)


class StrategyAssessmentError(ApplicationError):
    code = "STRATEGY_ASSESSMENT_ERROR"


class StrategyCausalityError(ApplicationError):
    code = "CAUSALITY_BLOCK"


class StrategyValidationError(ApplicationError):
    code = "STRATEGY_REQUEST_INVALID"


class StrategyAssessmentNotFoundError(ApplicationError):
    code = "STRATEGY_ASSESSMENT_NOT_FOUND"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(obj: Any) -> str:
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


class TradingStrategyAssessmentService:
    def __init__(
        self,
        store: TradingObservationStorePort,
        idem_store: TradingIdempotencyStorePort,
    ) -> None:
        self.store = store
        self.idem_store = idem_store

    def get_assessment(self, assessment_id: str) -> dict[str, Any]:
        getter = getattr(self.store, "get_strategy_assessment", None)
        if not callable(getter):
            raise StrategyAssessmentNotFoundError(
                f"strategy assessment not found: {assessment_id}"
            )
        row = getter(assessment_id)
        if not row:
            raise StrategyAssessmentNotFoundError(
                f"strategy assessment not found: {assessment_id}"
            )
        return row

    def assess(self, request: dict[str, Any], *, request_id: str | None = None) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise StrategyValidationError("request must be object")

        validation = validate_strategy_request(request)
        if not validation["ok"]:
            if validation.get("causality_errors"):
                raise StrategyCausalityError(";".join(validation["errors"][:6]))
            raise StrategyValidationError(";".join(validation["errors"][:6]))

        import os

        idem = str(request.get("idempotency_key") or "")
        if not idem:
            raise StrategyValidationError("idempotency_key required")

        payload_hash = content_hash(request)
        created = _utc()
        # Light mode: pure policy + response (TMX owns resume cache). Full mode: SQLite+JSONL.
        light = (os.environ.get("IM_STRATEGY_ASSESSMENT_LIGHT_PERSIST") or "").strip() == "1"

        if not light:
            claim = self.idem_store.claim_or_get(
                idempotency_key=idem,
                request_hash=payload_hash,
                created_at=created,
            )
            if claim.get("status") == "CONFLICT":
                raise IdempotencyConflictError(
                    "idempotency key reused with a different strategy request payload"
                )
            if claim.get("status") == "COMPLETE" and claim.get("response"):
                return claim["response"]
            if claim.get("status") == "PENDING":
                waited = self.idem_store.wait_complete(
                    idempotency_key=idem, request_hash=payload_hash
                )
                if waited and waited.get("status") == "CONFLICT":
                    raise IdempotencyConflictError(
                        "idempotency key reused with a different strategy request payload"
                    )
                if waited and waited.get("status") == "COMPLETE" and waited.get("response"):
                    return waited["response"]
                raise StrategyAssessmentError("idempotency pending; retry shortly")

        try:
            strategy = request.get("strategy") or {}
            profile_version = str(strategy.get("profile_version") or "")
            if profile_version.startswith("2"):
                from intelligence_maxxxing.domain_packs.trading.strategy_profiles_v2 import (
                    assess_strategy_request_v2,
                )

                policy_out = assess_strategy_request_v2(request)
            else:
                from intelligence_maxxxing.domain_packs.trading.strategy_profiles_v1 import (
                    assess_strategy_request,
                )

                policy_out = assess_strategy_request(request)

            req_id = request_id or str(request.get("request_id") or f"req_{uuid.uuid4().hex[:16]}")
            raw_setup_id = str(request.get("raw_setup_id") or "")
            assessment_id = "strat_asmt_" + hashlib.sha256(
                f"{payload_hash}|{raw_setup_id}|{idem}".encode()
            ).hexdigest()[:20]
            body = {
                "schema_version": STRATEGY_ASSESSMENT_SCHEMA_VERSION,
                "assessment_id": assessment_id,
                "request_id": req_id,
                "run_id": request.get("run_id"),
                "raw_setup_id": raw_setup_id,
                "idempotency_key": idem,
                "strategy": request.get("strategy"),
                "market": request.get("market"),
                "setup": request.get("setup"),
                "lineage": request.get("lineage"),
                **policy_out,
                "created_at_utc": created,
                "input_hash": payload_hash,
                "light_persist": light,
            }
            body["output_hash"] = _hash({k: v for k, v in body.items() if k != "output_hash"})

            check = validate_strategy_assessment(body)
            if not check["ok"]:
                raise StrategyAssessmentError(";".join(check["errors"][:6]))

            if not light:
                save_request = getattr(self.store, "save_strategy_request", None)
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
                save_strategy = getattr(self.store, "save_strategy_assessment", None)
                if callable(save_strategy):
                    save_strategy(body)
                self.store.save_idempotency(
                    {
                        "idempotency_key": idem,
                        "payload_hash": payload_hash,
                        "assessment_id": assessment_id,
                        "created_at_utc": created,
                        "coordination": "sqlite_wal_v1",
                        "lane": "strategy",
                    }
                )
                self.idem_store.complete(
                    idempotency_key=idem,
                    request_hash=payload_hash,
                    observation_id=None,
                    assessment_id=assessment_id,
                    policy_version=str(policy_out.get("profile_version") or ""),
                    response=body,
                    response_hash=str(body["output_hash"]),
                    completed_at=_utc(),
                )
            return body
        except Exception:
            if not light:
                self.idem_store.mark_failed(idempotency_key=idem, request_hash=payload_hash)
            raise
