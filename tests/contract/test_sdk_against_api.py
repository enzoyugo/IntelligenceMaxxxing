"""Contract tests: the public SDK against the real API over real local HTTP.

A uvicorn server runs the Engine on an ephemeral localhost port; the SDK
talks to it exactly like an external application would. No external services.
"""

import socket
import threading
import time
import uuid
from collections.abc import Iterator

import pytest
import uvicorn
from fastapi import FastAPI

from intelligence_maxxxing_client import (
    EngineConflictError,
    EngineNotFoundError,
    EngineUnavailableError,
    EngineValidationError,
    IntelligenceMaxxxingClient,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def live_engine_url(app: FastAPI) -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("test engine server failed to start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture()
def sdk_client(live_engine_url: str) -> Iterator[IntelligenceMaxxxingClient]:
    with IntelligenceMaxxxingClient(base_url=live_engine_url, timeout_seconds=10.0) as client:
        yield client


class TestSdkHealth:
    def test_health(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        health = sdk_client.health()
        assert health.service == "IntelligenceMaxxxing Engine"
        assert health.engine_version == "0.1.0"
        assert health.constitution_version == "1.1"
        assert health.meta.request_id.startswith("req_")


class TestSdkObservations:
    def test_submit_observation(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        accepted = sdk_client.submit_observation(
            subject="sleep",
            statement="Slept 7.5 hours",
            knowledge_class="OBSERVED_FACT",
            observed_by="sdk-test",
            scope="personal",
            idempotency_key=f"sdk-{uuid.uuid4().hex}",
        )
        assert accepted.observation_id.startswith("obs_")
        assert accepted.audit_id.startswith("aud_")
        assert accepted.replayed is False

    def test_submit_retry_is_idempotent(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        key = f"sdk-{uuid.uuid4().hex}"
        kwargs: dict[str, str] = {
            "subject": "sleep",
            "statement": "Slept 6 hours",
            "knowledge_class": "OBSERVED_FACT",
            "observed_by": "sdk-test",
            "scope": "personal",
        }
        first = sdk_client.submit_observation(idempotency_key=key, **kwargs)
        retry = sdk_client.submit_observation(idempotency_key=key, **kwargs)
        assert retry.replayed is True
        assert retry.observation_id == first.observation_id

    def test_conflict_is_typed(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        key = f"sdk-{uuid.uuid4().hex}"
        sdk_client.submit_observation(
            subject="sleep",
            statement="Slept 6 hours",
            knowledge_class="OBSERVED_FACT",
            observed_by="sdk-test",
            scope="personal",
            idempotency_key=key,
        )
        with pytest.raises(EngineConflictError):
            sdk_client.submit_observation(
                subject="sleep",
                statement="A DIFFERENT statement",
                knowledge_class="OBSERVED_FACT",
                observed_by="sdk-test",
                scope="personal",
                idempotency_key=key,
            )

    def test_validation_error_is_typed(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        with pytest.raises(EngineValidationError):
            sdk_client.submit_observation(
                subject="sleep",
                statement="inference disguised as observation",
                knowledge_class="INFERENCE",
                observed_by="sdk-test",
                scope="personal",
                idempotency_key=f"sdk-{uuid.uuid4().hex}",
            )


class TestSdkAudits:
    def test_get_audit(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        accepted = sdk_client.submit_observation(
            subject="sleep",
            statement="Slept 7.5 hours",
            knowledge_class="OBSERVED_FACT",
            observed_by="sdk-test",
            scope="personal",
            idempotency_key=f"sdk-{uuid.uuid4().hex}",
        )
        audit = sdk_client.get_audit(accepted.audit_id)
        assert audit.audit_id == accepted.audit_id
        assert audit.action == "observations.submit"
        assert audit.output_object_ids == [accepted.observation_id]
        assert len(audit.events) == 1
        assert audit.events[0].event_type == "ObservationAccepted"

    def test_missing_audit_is_typed(self, sdk_client: IntelligenceMaxxxingClient) -> None:
        with pytest.raises(EngineNotFoundError):
            sdk_client.get_audit("aud_missing")


class TestSdkResilience:
    def test_unreachable_engine_is_typed(self) -> None:
        client = IntelligenceMaxxxingClient(base_url="http://127.0.0.1:1", timeout_seconds=0.2)
        with pytest.raises(EngineUnavailableError):
            client.health()
        client.close()
