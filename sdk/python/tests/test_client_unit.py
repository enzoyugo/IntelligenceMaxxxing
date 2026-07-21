"""Hermetic unit tests for the standalone client (no Engine, no network).

These run against an httpx MockTransport so the wheel can be certified in a
clean virtualenv that has ONLY httpx + pydantic installed.
"""

import sys

import httpx
import pytest

from intelligence_maxxxing_client import (
    EngineConflictError,
    EngineForbiddenError,
    EngineNotFoundError,
    EngineUnavailableError,
    EngineValidationError,
    IntelligenceMaxxxingClient,
    new_idempotency_key,
)

_META = {
    "request_id": "req_abc",
    "engine_version": "0.1.0",
    "api_version": "v1",
    "domain_pack": "life",
    "generated_at": "2026-01-01T00:00:00Z",
    "audit_id": "aud_1",
}


def _ok(data: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "data": data, "error": None, "meta": _META})


def _err(status: int, code: str) -> httpx.Response:
    return httpx.Response(
        status,
        json={
            "ok": False,
            "data": None,
            "error": {"code": code, "message": "nope", "details": {}},
            "meta": _META,
        },
    )


def _client(handler: object) -> IntelligenceMaxxxingClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    http = httpx.Client(base_url="http://engine.test", transport=transport)
    return IntelligenceMaxxxingClient(credential_secret="imx_sk_test", http_client=http)


def test_no_core_import() -> None:
    import intelligence_maxxxing_client as pkg

    core_modules = [
        m
        for m in sys.modules
        if m == "intelligence_maxxxing" or m.startswith("intelligence_maxxxing.")
    ]
    assert core_modules == [], core_modules
    assert pkg.IntelligenceMaxxxingClient is not None


def test_submit_observation_sends_bearer_and_idem_key() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        seen["idem"] = request.headers.get("idempotency-key", "")
        return _ok(
            {"observation_id": "obs_1", "event_id": "evt_1", "audit_id": "aud_1", "replayed": False}
        )

    client = _client(handler)
    key = new_idempotency_key()
    accepted = client.submit_observation(
        subject="daily_check_in",
        statement="Daily check-in recorded",
        knowledge_class="OBSERVED_FACT",
        observed_by="lifemaxxxing-backend",
        scope="personal",
        domain_pack="life",
        idempotency_key=key,
        environment="PRODUCTION",
        metadata={"observation_purpose": "USER_OBSERVATION"},
    )
    assert accepted.observation_id == "obs_1"
    assert accepted.replayed is False
    assert seen["auth"] == "Bearer imx_sk_test"
    assert seen["idem"] == key


def test_submit_observation_includes_environment() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content.decode())
        return _ok(
            {"observation_id": "obs_1", "event_id": "evt_1", "audit_id": "aud_1", "replayed": False}
        )

    client = _client(handler)
    client.submit_observation(
        subject="daily_check_in",
        statement="Daily check-in recorded",
        knowledge_class="OBSERVED_FACT",
        observed_by="iso-smoke",
        scope="personal",
        domain_pack="life",
        idempotency_key=new_idempotency_key(),
        environment="TEST",
        metadata={"observation_purpose": "SMOKE_TEST", "subject_scope": "TEST_PROFILE"},
    )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["context"]["environment"] == "TEST"
    assert body["metadata"]["observation_purpose"] == "SMOKE_TEST"


def test_get_audit_parses_view() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(
            {
                "audit_id": "aud_1",
                "request_id": "req_abc",
                "engine_version": "0.1.0",
                "api_version": "v1",
                "schema_version": "1.0",
                "domain_pack": "life",
                "actor_type": "APPLICATION",
                "actor_id": "app_1",
                "action": "observation.submit",
                "input_object_ids": [],
                "output_object_ids": ["obs_1"],
                "event_ids": ["evt_1"],
                "timestamp": "2026-01-01T00:00:00Z",
                "events": [],
            }
        )

    client = _client(handler)
    audit = client.get_audit("aud_1")
    assert audit.audit_id == "aud_1"
    assert audit.action == "observation.submit"


@pytest.mark.parametrize(
    ("status", "code", "exc"),
    [
        (403, "PERMISSION_DENIED", EngineForbiddenError),
        (404, "AUDIT_NOT_FOUND", EngineNotFoundError),
        (409, "IDEMPOTENCY_CONFLICT", EngineConflictError),
        (422, "VALIDATION_ERROR", EngineValidationError),
    ],
)
def test_typed_errors(status: int, code: str, exc: type[Exception]) -> None:
    client = _client(lambda request: _err(status, code))
    with pytest.raises(exc) as info:
        client.get_audit("aud_x")
    assert info.value.code == code  # type: ignore[attr-defined]
    assert info.value.status_code == status  # type: ignore[attr-defined]


def test_network_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(EngineUnavailableError):
        client.health()


def test_non_json_response_is_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    from intelligence_maxxxing_client import EngineAPIError

    client = _client(handler)
    with pytest.raises(EngineAPIError) as info:
        client.get_audit("aud_1")
    assert info.value.code == "INVALID_RESPONSE"
