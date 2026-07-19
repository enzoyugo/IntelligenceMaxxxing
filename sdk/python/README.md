# intelligence-maxxxing-client

Standalone public Python client for the **IntelligenceMaxxxing Engine** HTTP API (v1).

This package speaks the Engine's public, versioned HTTP contract and nothing else.
It **never** imports the Engine Core (`intelligence_maxxxing`) and does not depend on
FastAPI, SQLAlchemy, Alembic or psycopg. That boundary is enforced by import-linter
and constitutional tests in the Engine repository, and by this package's dependency
list (only `httpx` and `pydantic`).

## Install

From a built wheel (preferred for external applications):

```bash
pip install intelligence_maxxxing_client-<version>-py3-none-any.whl
```

Requires Python >= 3.10.

## Usage

```python
from intelligence_maxxxing_client import IntelligenceMaxxxingClient, new_idempotency_key

with IntelligenceMaxxxingClient(
    base_url="http://127.0.0.1:8100",
    credential_secret="imx_sk_...",  # server-side only; never ship to a mobile client
    timeout_seconds=10.0,
) as client:
    accepted = client.submit_observation(
        subject="daily_check_in",
        statement="Daily check-in recorded",
        knowledge_class="OBSERVED_FACT",
        observed_by="lifemaxxxing-backend",
        scope="personal",
        domain_pack="life",
        idempotency_key=new_idempotency_key(),
    )
    audit = client.get_audit(accepted.audit_id)
```

## Security

- The credential secret is passed as a `Bearer` token and is **never logged** by this client.
- Do not embed the secret in a mobile bundle or any `EXPO_PUBLIC_*` variable. It belongs
  only in a trusted server-side environment (e.g. a backend `.env`).

## Typed errors

All non-2xx envelopes are raised as typed exceptions:

| Exception | Meaning |
|---|---|
| `EngineUnauthorizedError` | 401 authentication failed |
| `EngineForbiddenError` | 403 missing scope |
| `EngineNotFoundError` | 404 not found (also out-of-scope reads) |
| `EngineConflictError` | 409 idempotency conflict |
| `EngineValidationError` | 422 request rejected |
| `EngineServiceUnavailableError` | 503 not ready |
| `EngineUnavailableError` | network error / timeout (engine unreachable) |

## Building

From the Engine repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\sdk\build_client_sdk.ps1
powershell -ExecutionPolicy Bypass -File scripts\sdk\test_client_sdk.ps1
```

The build produces `dist/sdk/intelligence_maxxxing_client-<version>-py3-none-any.whl`
and prints its SHA-256. The test script installs the wheel into a clean virtualenv and
verifies that the Engine Core is absent.
