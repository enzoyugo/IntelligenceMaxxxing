# IntelligenceMaxxxing Engine

Constitutionally governed, application-agnostic intelligence backend.

## What it is

IntelligenceMaxxxing is an **independent backend service** that will act as the
source of truth for accepted observations, evidence, hypotheses, experiments,
beliefs, recommendations, recorded decisions, outcomes, learning, permissions
and audit — for every client application (LifeMaxxxing, TradingMaxxxing, the
betting bot, and future apps).

Stage 1 (current) extends the Stage 0 foundation with **authenticated API
access**, **governed identity and scopes**, a **versioned event catalog**, an
**integrity hash chain**, **rebuildable projections**, **PostgreSQL append-only
enforcement**, and **migration safety gates** — still as a real, running,
tested private backend.

Stage 0 delivered: versioned public API, strict canonical schemas, append-only
event store, recoverable audit trail, and idempotent writes.

## What it is not

- Not a frontend, and it never will contain one.
- Not an AI agent: there is **no** LLM, belief engine, hypothesis generation,
  recommendation logic, trading or betting capability. Contracts for those
  exist; nothing simulates that they work.
- Not integrated with any client application yet.
- Not deployed remotely: Stage 1 assumes a **local private backend** on
  `127.0.0.1` with CLI-only administration.

## Document authority

Everything in `docs/constitutional/` is frozen and hashed
(`CONSTITUTIONAL_MANIFEST.sha256`). On conflict, authority order is:

1. `INTELLIGENCE_ENGINE_CONSTITUTION.md`
2. `CONSTITUTIONAL_CHANGES.md`
3. `ENGINE_GOVERNANCE.md`
4. `EPISTEMIC_STANDARD.md`
5. `DOMAIN_PACK_STANDARD.md`
6. `ENGINE_SERVICE_CONTRACT.md`
7. `TECHNICAL_ARCHITECTURE.md`

If code contradicts the Constitution, the code changes.

## Architecture (Stage 1)

Layered modular monolith with boundaries enforced by import-linter **and**
constitutional tests:

```text
api            -> translates HTTP to use cases (no domain logic, no table access)
application    -> use cases + ports (no FastAPI, no SQLAlchemy)
domain         -> pure Python canonical objects (no web, no ORM, no network)
infrastructure -> SQLAlchemy/PostgreSQL implementations of the ports
contracts      -> public versioned schemas + event catalog (never ORM models)
domain_packs   -> contract-only placeholders (life, trading, sports_betting)
sdk/python     -> public client; consumes HTTP only, never imports the Core
```

The smoke path proven by tests and live checks:

```text
Application -> Bearer auth -> Public API -> Observation validation
            -> Append-only event -> Audit record -> Projection update
            -> Versioned response envelope
```

Identity administration (bootstrap, credentials, scopes) is **CLI-only** — no
HTTP admin endpoints.

## Install

```powershell
cd E:\IntelligenceMaxxxing
python -m pip install -e ".[dev]"
# or: powershell -ExecutionPolicy Bypass -File scripts\dev\setup_engine.ps1
```

## Run PostgreSQL (Docker)

```powershell
docker compose up -d postgres
# or: powershell -ExecutionPolicy Bypass -File scripts\dev\start_postgres.ps1
```

PostgreSQL 16 on `127.0.0.1:5432`. See `docs/runbooks/POSTGRESQL_SETUP.md`.

## Migrate

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
# or: python -m alembic upgrade head
```

Migration `0002_stage1` adds identity, projections, integrity columns,
append-only SQL triggers, and database roles.

## Bootstrap credentials (first time)

```powershell
python -m intelligence_maxxxing.cli bootstrap-owner --tenant-name "Private Instance" --owner-name "Owner"
python -m intelligence_maxxxing.cli register-application --display-name "Demo" --owner-id usr_...
python -m intelligence_maxxxing.cli create-credential --application-id app_...
python -m intelligence_maxxxing.cli grant-scope --application-id app_... --scope SUBMIT_OBSERVATION
python -m intelligence_maxxxing.cli grant-scope --application-id app_... --scope READ_INTELLIGENCE
python -m intelligence_maxxxing.cli grant-scope --application-id app_... --scope READ_AUDIT
```

The secret is shown **once**. See `docs/runbooks/CREDENTIAL_BOOTSTRAP.md`.

## Start the Engine

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_engine.ps1
# Engine listens on http://127.0.0.1:8100
```

## Run tests and quality gates

```powershell
python -m pytest -q                     # no external services required
powershell -ExecutionPolicy Bypass -File scripts\audit\run_quality_gates.ps1
```

## Use the API

Health (no auth):

```powershell
curl.exe http://127.0.0.1:8100/health/live
curl.exe http://127.0.0.1:8100/health/ready
```

Detailed health (requires Bearer credential):

```powershell
curl.exe http://127.0.0.1:8100/api/v1/health -H "Authorization: Bearer imx_sk_..."
```

Submit an observation (requires `SUBMIT_OBSERVATION` scope + `Idempotency-Key`):

```powershell
curl.exe -X POST http://127.0.0.1:8100/api/v1/observations `
  -H "Authorization: Bearer imx_sk_..." `
  -H "Content-Type: application/json" `
  -H "Idempotency-Key: demo-001" `
  -d '{\"schema_version\":\"1.0\",\"subject\":\"sleep\",\"statement\":\"Slept 7.5 hours\",\"knowledge_class\":\"OBSERVED_FACT\",\"observed_by\":\"demo\",\"context\":{\"scope\":\"personal\"}}'
```

List observations (requires `READ_INTELLIGENCE`):

```powershell
curl.exe http://127.0.0.1:8100/api/v1/observations -H "Authorization: Bearer imx_sk_..."
```

Retrieve the audit (requires `READ_AUDIT`):

```powershell
curl.exe http://127.0.0.1:8100/api/v1/audits/aud_... -H "Authorization: Bearer imx_sk_..."
```

Or use the public SDK (which never imports the Core):

```python
from intelligence_maxxxing_client import IntelligenceMaxxxingClient

with IntelligenceMaxxxingClient(
    base_url="http://127.0.0.1:8100",
    credential_secret="imx_sk_...",
) as client:
    print(client.health().status)
    accepted = client.submit_observation(
        subject="sleep",
        statement="Slept 7.5 hours",
        knowledge_class="OBSERVED_FACT",
        observed_by="demo",
        scope="personal",
        idempotency_key="demo-002",
    )
    print(client.get_audit(accepted.audit_id).action)
```

## Implemented in Stage 1

- **Authentication:** Bearer API credentials; SHA-256 hash storage; secret shown once.
- **Authorization:** scope enforcement on all `/api/v1/*` endpoints (`SUBMIT_OBSERVATION`, `READ_INTELLIGENCE`, `READ_AUDIT`).
- **Identity model:** tenant, user, application, service, actor; CLI-only admin.
- **Event catalog:** 12 registered event types; unregistered payloads rejected.
- **Integrity chain:** SHA-256 per `(tenant, owner, application)` stream (Stage 1.1); CLI `verify-integrity`.
- **Projections:** `accepted_observations` derived from events; rebuildable; checkpointed.
- **PostgreSQL enforcement:** REVOKE + triggers on ledger tables; roles `engine_migrator`, `engine_runtime`, `engine_readonly`.
- **Health:** `/health/live`, `/health/ready` (public); `/api/v1/health` (authenticated, measured).
- **Migration safety:** destructive downgrades blocked by default (`MigrationSafetyPolicy`).
- **New API endpoints:** `GET /api/v1/observations`, `GET /api/v1/observations/{id}`.
- **Composite idempotency scope:** `application_id + owner_id + action + key`.

Everything from Stage 0 remains: append-only event store, audit trail, canonical
schemas, constitutional tests, public Python SDK.

## Hardened in Stage 1.1 (adversarial fixes)

An independent audit found blocking defects in Stage 1; Stage 1.1 corrects them
without expanding scope (see `docs/reviews/STAGE_1_1_ISOLATION_INTEGRITY_HARDENING_REPORT.md`):

- **Application-scoped audits:** audit reads are scoped by `(tenant, owner, application)`; an
  application cannot read another application's audit under the same owner — out-of-scope ids
  return **404** (no existence leak).
- **Concurrency-safe integrity chain:** a transactional `event_stream_heads` row
  (`SELECT … FOR UPDATE`) serializes same-stream writers so 20 concurrent appends form one
  valid chain — proven on real PostgreSQL.
- **Real quarantine kill-switch:** a detected break sets the stream `QUARANTINED` and rejects
  new writes (`STREAM_QUARANTINED` → 409); release is CLI-only and requires `ADMINISTER_ENGINE`
  plus a successful full verify.
- **Incremental integrity anchor:** `integrity_checkpoints` anchor INCREMENTAL verification so
  a legitimate mid-stream start is never mistaken for corruption.
- **Non-destructive projection verify:** `verify` compares a shadow build to live without
  mutating it; `rebuild` promotes atomically.
- **Scoped aggregates:** aggregate identity includes `(tenant, owner, application)`.

See `docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md`.

## Integrated in Stage 2 (first external client)

LifeMaxxxing is the first registered client application
(see `docs/reviews/STAGE_2_LIFEMAXXXING_INTEGRATION_REPORT.md`):

- **Standalone SDK:** `sdk/python` builds an `intelligence-maxxxing-client`
  wheel (httpx + pydantic only, Python >=3.10, no Engine Core) via
  `scripts/sdk/build_client_sdk.ps1`; certified in a clean virtualenv by
  `scripts/sdk/test_client_sdk.ps1`.
- **Life namespace:** LifeMaxxxing submits minimized `domain_pack="life"`
  observations through the public contract; the Engine contains zero
  Life-specific logic.
- **Cross-repo gate:** `scripts/audit/run_lifemaxxxing_contract_gates.ps1`
  proves the vertical slice (sync, replay idempotency, data minimization,
  audit recoverability, cross-app isolation, offline behaviour, secret scan)
  on real PostgreSQL and real HTTP.
- **Compatibility lock:** `docs/integrations/lifemaxxxing_compatibility_lock.json`.

## Explicitly out of scope (Stage 1 / Stage 1.1)

Frontend/console, further client application integrations, real Domain Pack logic,
hypothesis generation, Belief Engine, Cross-Domain Coordinator, knowledge graph,
vector DB, LLMs, trading/bet execution, microservices, cloud deployment, active
autonomy, real recommendations, signed JWT tokens, HTTP admin endpoints, active
rate limiting (hook contract only), automatic/scheduled integrity verification.

## Further reading

- `docs/architecture/IDENTITY_AND_PERMISSION_MODEL.md` — auth, scopes, CLI admin.
- `docs/architecture/EVENT_CATALOG.md` — registered event types.
- `docs/architecture/PROJECTION_MODEL.md` — derived read models.
- `docs/architecture/POSTGRES_APPEND_ONLY_ENFORCEMENT.md` — SQL-level ledger protection.
- `docs/architecture/CONSTITUTION_TRACEABILITY_MATRIX.md` — principle → code → test mapping.
- `docs/architecture/OFFLINE_SYNC_CONTRACT.md` — offline/sync contract.
- `docs/runbooks/POSTGRESQL_SETUP.md` — database setup.
- `docs/runbooks/CREDENTIAL_BOOTSTRAP.md` — first-time credential setup.
- `docs/runbooks/PROJECTION_REBUILD.md` — rebuild projections from events.
- `docs/runbooks/INTEGRITY_VERIFICATION.md` — verify the hash chain, quarantine and release.
- `docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md` — concurrent chain heads and quarantine (Stage 1.1).
- `docs/runbooks/MIGRATION_SAFETY.md` — destructive migration gates.
- `docs/runbooks/LOCAL_DEVELOPMENT.md` — day-to-day commands.
- `docs/integrations/LIFEMAXXXING_INTEGRATION.md` — first external client (Stage 2).
- `docs/reviews/` — sprint reports and conflict records.
