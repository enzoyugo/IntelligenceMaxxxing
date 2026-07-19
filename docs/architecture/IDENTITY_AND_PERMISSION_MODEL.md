# Identity and Permission Model — Stage 1

**Status:** IMPLEMENTED (Stage 1)  
**Authority:** Engine Service Contract §5–§6, Technical Architecture §9  
**Code:** `src/intelligence_maxxxing/domain/identity/`, `application/auth/`, `application/use_cases/identity_admin.py`, `permissions/`

---

## 1. Purpose

Stage 1 introduces a governed identity layer for the private backend. Every HTTP write is authenticated; the effective actor always comes from the auth context, never from the request body. Identity administration is CLI-only — there are no public HTTP admin endpoints.

---

## 2. Identity types

All identity objects are frozen Pydantic domain models (`domain/identity/models.py`).

| Type | Role | Key fields |
|---|---|---|
| `TenantIdentity` | Logical tenant boundary | `id`, `display_name`, `status`, `audit_id` |
| `UserIdentity` | Human owner | `tenant_id`, `display_name`, `status` |
| `ApplicationIdentity` | External client application | `tenant_id`, **`owner_id`** (assigned at registration), `status` |
| `ServiceIdentity` | Internal Engine service (projector, integrity checker, …) | `tenant_id` |
| `ActorIdentity` | Resolved authenticated actor of an operation | `actor_id`, `actor_type`, `application_id`, `owner_id`, `tenant_id` |

`ActorIdentity` is built exclusively from the authentication context. Request bodies cannot inject or override `actor_id`, `owner_id`, `tenant_id`, or `application_id`.

System identities used for CLI-driven governance events live in `domain/identity/system.py` (`SYSTEM_TENANT_ID`, `SYSTEM_OWNER_ID`, `SYSTEM_APPLICATION_ID`, `SYSTEM_ACTOR`).

---

## 3. Application registration and ownership

- Applications are registered via the local CLI (`register-application`), not HTTP.
- **`owner_id` is assigned at registration** from the `--owner-id` argument supplied by the operator. Callers cannot choose or override `owner_id` through the public API.
- Every registration appends an `ApplicationRegistered` event to `engine_events` and an audit record.
- Scopes are stored on the application row and mirrored in `PermissionGranted` / `PermissionRevoked` events.

---

## 4. API credentials

Stage 1 uses application API credentials (Bearer secrets), not signed JWTs.

| Property | Value |
|---|---|
| Public identifier | `cred_<24 lowercase hex chars>` |
| Secret format | `imx_sk_<24 hex chars><43 url-safe random chars>` |
| Storage | SHA-256 hash of the **full secret** only; plaintext is never persisted |
| Request header | `Authorization: Bearer <secret>` |
| Display policy | Secret shown **once** at creation/rotation; never retrievable afterward |

The credential id is embedded in the secret prefix so lookup is O(1) by primary key, followed by a constant-time hash comparison (`application/auth/service.py`).

Credential lifecycle events (`ApplicationCredentialCreated`, `ApplicationCredentialRotated`, `ApplicationCredentialRevoked`) record metadata only — never the secret or its hash.

---

## 5. Permission scopes

Scopes are defined in `permissions/__init__.py` as the `PermissionScope` enum. They are granted to applications through the CLI (`grant-scope`); a credential cannot elevate its own scopes (scopes are read from the identity store on every request).

| Scope | Stage 1 enforcement |
|---|---|
| `READ_INTELLIGENCE` | `GET /api/v1/observations`, `GET /api/v1/observations/{id}` |
| `SUBMIT_OBSERVATION` | `POST /api/v1/observations` |
| `READ_AUDIT` | `GET /api/v1/audits/{audit_id}` |
| `SUBMIT_EVIDENCE` | Not enforced (no endpoint yet) |
| `EXECUTE_ACTION` | Not enforced (no endpoint yet) |
| `SUBMIT_DECISION` | Not enforced (no endpoint yet) |
| `SUBMIT_OUTCOME` | Not enforced (no endpoint yet) |
| `REQUEST_DELETION` | Not enforced (no endpoint yet) |
| `MANAGE_DOMAIN_PACK` | Not enforced (no endpoint yet) |
| `APPROVE_EXECUTION` | Not enforced (no endpoint yet) |
| `ADMINISTER_ENGINE` | Required for destructive migration authorization (policy gate); not used by HTTP endpoints |

Any authenticated credential may call `GET /api/v1/health` (detailed health); no specific scope is required beyond valid authentication.

Deny-closed: missing scope → HTTP 403 (`PermissionDeniedError`).

---

## 6. Authentication flow

```text
Authorization: Bearer imx_sk_<cred_hex><random>
        │
        ▼
parse credential_id from secret prefix
        │
        ▼
load credential → constant-time SHA-256 compare
        │
        ▼
verify credential ACTIVE, application ACTIVE
        │
        ▼
load scopes from identity store → AuthContext
        │
        ▼
use case receives AuthContext; actor = auth.actor
```

`AuthContext` fields (`application_id`, `owner_id`, `tenant_id`, `scopes`) propagate into event isolation columns and audit records.

---

## 7. CLI-only administration

Identity administration use cases (`IdentityAdminService`) are invoked **only** by the local CLI (`python -m intelligence_maxxxing.cli`). There are no public HTTP endpoints for:

- bootstrapping the owner
- registering applications
- creating, rotating, or revoking credentials
- granting or revoking scopes

See `docs/runbooks/CREDENTIAL_BOOTSTRAP.md` for operator commands.

---

## 8. Rate limiting hook (contract only)

`RateLimitHookPort` (`application/ports/stores.py`) defines a pluggable rate-limit check:

```python
def check(self, application_id: str, action: str) -> None:
    """Raise a typed error to reject; return to allow."""
```

Stage 1 ships the **contract only**. No default implementation is wired into the request path; the hook is a no-op until a future stage plugs in real limits without API changes.

---

## 9. Data isolation

Events and audit records carry `tenant_id`, `owner_id`, and `application_id`. Read paths filter by the authenticated application's owner scope so one application cannot read another owner's data (`tests/integration/test_permissions_isolation.py`).

### 9.1 Stage 1.1 — application-scoped audit reads

Stage 1 isolated audits by owner but **not** by application: two applications under the same owner could read each other's audits. Stage 1.1 closes this. Every audit and audit-event read is scoped by the full triple `(tenant_id, owner_id, application_id, audit_id)`:

- `AuditStorePort.get_by_audit_id(tenant_id, owner_id, application_id, audit_id)`
- `EventStorePort.list_by_audit(tenant_id, owner_id, application_id, audit_id)`
- `GetAuditUseCase` passes the authenticated `AuthContext` triple.

An out-of-scope audit id (another application under the same owner, or another tenant) behaves as **missing → HTTP 404**, never 403, so existence is not leaked across applications or tenants. Regression: `tests/integration/test_audit_isolation.py` and `tests/postgres/test_stage1_1_hardening.py::test_cross_application_audit_exploit_regression` (SQLite and real PostgreSQL).

Aggregate identity is likewise scoped by `(tenant_id, owner_id, application_id, aggregate_type, aggregate_id, aggregate_version)`; see `docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md`.

---

## 10. Explicitly not in Stage 1

- Signed short-lived tokens / OAuth / SSO
- Multi-user RBAC beyond application scopes
- HTTP admin endpoints
- Secret manager integration
- Active rate limiting (hook exists; default no-op)
- Remote deployment hardening (local private interface assumed)
