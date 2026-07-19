"""Stage 2 certification: the standalone SDK and the LifeMaxxxing namespace.

These tests prove, without any external application present, that:
  * the client wheel is buildable and contains ONLY the client (no Engine Core),
  * an external app can submit / read / audit through the PUBLIC contract only,
  * a `life`-namespaced observation is accepted as an opaque domain pack,
  * the credential scope profile an external client needs is minimal.

The SDK is exercised in-process over an httpx ASGI transport, i.e. exactly the
public HTTP contract, but hermetically (no sockets, no external services).
"""

from __future__ import annotations

import subprocess
import sys
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.permissions import PermissionScope
from intelligence_maxxxing_client import (
    EngineForbiddenError,
    EngineNotFoundError,
    EngineValidationError,
    IntelligenceMaxxxingClient,
)
from tests.fixtures.identity import BootstrappedIdentity

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The scope profile that an EXTERNAL client (e.g. the LifeMaxxxing backend) needs.
LIFEMAXXXING_MINIMAL_SCOPES = frozenset(
    {
        PermissionScope.SUBMIT_OBSERVATION.value,
        PermissionScope.READ_AUDIT.value,
        PermissionScope.READ_INTELLIGENCE.value,
    }
)


@pytest.fixture()
def cert_client(
    app: FastAPI, identity: BootstrappedIdentity
) -> Iterator[IntelligenceMaxxxingClient]:
    # TestClient is a sync httpx.Client that runs the real ASGI app (incl.
    # lifespan) in-process, so the SDK exercises the public HTTP contract.
    with (
        TestClient(app, raise_server_exceptions=False) as http,
        IntelligenceMaxxxingClient(credential_secret=identity.secret, http_client=http) as client,
    ):
        yield client


def _submit_life_checkin(client: IntelligenceMaxxxingClient) -> object:
    return client.submit_observation(
        subject="daily_check_in",
        statement="Daily check-in recorded",
        knowledge_class="OBSERVED_FACT",
        observed_by="lifemaxxxing-backend",
        scope="personal",
        domain_pack="life",
        idempotency_key=f"life-{uuid.uuid4().hex}",
        metadata={"life_event_type": "life.daily_check_in.completed.v1"},
    )


def test_standalone_sdk_submits_observation(cert_client: IntelligenceMaxxxingClient) -> None:
    accepted = _submit_life_checkin(cert_client)
    assert accepted.observation_id.startswith("obs_")  # type: ignore[attr-defined]
    assert accepted.event_id.startswith("evt_")  # type: ignore[attr-defined]
    assert accepted.audit_id.startswith("aud_")  # type: ignore[attr-defined]
    assert accepted.replayed is False  # type: ignore[attr-defined]


def test_life_namespace_observation_uses_public_contract(
    cert_client: IntelligenceMaxxxingClient,
) -> None:
    accepted = _submit_life_checkin(cert_client)
    viewed = cert_client.get_observation(accepted.observation_id)  # type: ignore[attr-defined]
    assert viewed.domain_pack == "life"
    assert viewed.subject == "daily_check_in"


def test_standalone_sdk_gets_audit(cert_client: IntelligenceMaxxxingClient) -> None:
    accepted = _submit_life_checkin(cert_client)
    audit = cert_client.get_audit(accepted.audit_id)  # type: ignore[attr-defined]
    assert audit.audit_id == accepted.audit_id  # type: ignore[attr-defined]
    assert audit.output_object_ids == [accepted.observation_id]  # type: ignore[attr-defined]
    assert len(audit.events) == 1
    assert audit.events[0].event_type == "ObservationAccepted"


def test_standalone_sdk_typed_errors_pass(cert_client: IntelligenceMaxxxingClient) -> None:
    # 404 for an unknown audit.
    with pytest.raises(EngineNotFoundError):
        cert_client.get_audit("aud_missing")
    # 422 for an epistemic violation (INFERENCE submitted as an observation).
    with pytest.raises(EngineValidationError):
        cert_client.submit_observation(
            subject="daily_check_in",
            statement="inference disguised as observation",
            knowledge_class="INFERENCE",
            observed_by="lifemaxxxing-backend",
            scope="personal",
            domain_pack="life",
            idempotency_key=f"life-{uuid.uuid4().hex}",
        )


def test_missing_scope_is_forbidden(app: FastAPI) -> None:
    """An app WITHOUT SUBMIT_OBSERVATION is rejected with a typed 403."""
    from tests.fixtures.identity import bootstrap_test_identity, register_application_for

    base = bootstrap_test_identity(app)
    read_only = register_application_for(
        app,
        owner_id=base.owner_id,
        display_name="read-only-app",
        scopes=(PermissionScope.READ_AUDIT, PermissionScope.READ_INTELLIGENCE),
    )
    with (
        TestClient(app, raise_server_exceptions=False) as http,
        IntelligenceMaxxxingClient(credential_secret=read_only.secret, http_client=http) as client,
        pytest.raises(EngineForbiddenError),
    ):
        _submit_life_checkin(client)


def test_lifemaxxxing_credential_scope_is_minimal() -> None:
    """The external-client profile must be least-privilege."""
    privileged = {
        PermissionScope.ADMINISTER_ENGINE.value,
        PermissionScope.MANAGE_DOMAIN_PACK.value,
        PermissionScope.APPROVE_EXECUTION.value,
        PermissionScope.EXECUTE_ACTION.value,
    }
    # Every requested scope is a real, valid engine scope.
    valid = {s.value for s in PermissionScope}
    assert LIFEMAXXXING_MINIMAL_SCOPES.issubset(valid)
    # The profile grants no engine-administration or registration authority.
    assert LIFEMAXXXING_MINIMAL_SCOPES.isdisjoint(privileged)
    # Submitting + reading audits/intelligence is exactly what a client needs.
    assert PermissionScope.SUBMIT_OBSERVATION.value in LIFEMAXXXING_MINIMAL_SCOPES
    assert PermissionScope.READ_AUDIT.value in LIFEMAXXXING_MINIMAL_SCOPES


def test_standalone_sdk_wheel_contains_no_core(tmp_path: Path) -> None:
    """Build the client wheel and prove the Engine Core is not vendored in."""
    build = pytest.importorskip("build", reason="`build` needed to certify the wheel")
    assert build is not None
    out = tmp_path / "wheelhouse"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(out),
            str(REPO_ROOT / "sdk" / "python"),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1, wheels
    names = zipfile.ZipFile(wheels[0]).namelist()
    code_top_level = {n.split("/")[0] for n in names if "/" in n and ".dist-info/" not in n}
    assert code_top_level == {"intelligence_maxxxing_client"}, code_top_level
    leaked = [
        n
        for n in names
        if n.startswith("intelligence_maxxxing/")
        or n.startswith("src/")
        or n.startswith("intelligence_maxxxing-")
    ]
    assert leaked == [], leaked
