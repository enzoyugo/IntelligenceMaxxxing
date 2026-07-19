# STAGE 1 — Trusted Core Ledger Report

## Executive verdict

```text
STAGE_1_TRUSTED_CORE_LEDGER_PASS
```

## Baseline and commits

| Item | Value |
| --- | --- |
| Stage 0 final reference | `4ac55fc` |
| Stage 1 baseline | `f221b2f` — `STAGE_1_BASELINE: freeze validated Stage 0` |
| Implementation | `1e778fc` — `STAGE_1_IDENTITY_SECURITY` (includes ledger + projections; tightly coupled) |
| Report | `6d1239c` — `STAGE_1_REPORT` |
| Canonical branch | `main` |
| Remote | `origin` → `https://github.com/enzoyugo/IntelligenceMaxxxing.git` |

Suggested intermediate commits (`LEDGER` / `PROJECTIONS` as separate SHAs) were combined into the identity/security implementation commit because identity, ledger schema, auth, projections and API surfaces share one migration and one transactional write path.

## Push and working tree

| Item | Status |
| --- | --- |
| Push status | **PUSHED** (`origin/main` @ `7c6a8e8`) |
| Working tree | clean after final commit |

## PostgreSQL verification

| Item | Value |
| --- | --- |
| PostgreSQL verification | **REAL POSTGRESQL 16 ALPINE** |
| Exact version | PostgreSQL 16.14 on x86_64-pc-linux-musl |
| Method | Docker Compose service `postgres` (`postgres:16-alpine`) |
| Container | `intelligence_maxxxing_postgres` |
| Host binding | `127.0.0.1:5432` |
| Docker verification | **PASS** (`pg_isready` accepting connections) |
| Connection (redacted) | `postgresql+psycopg://intelligence:***@127.0.0.1:5432/intelligence_maxxxing_stage1_gates` |
| Gate script | `scripts/audit/run_postgres_gates.ps1` |
| Migrations applied | `0001_stage0` → `0002_stage1` from zero on a dedicated gate database |
| Cleanup | gate database dropped/recreated each gate run |

## Migrations, roles and grants

- Migration `0002_stage1_trusted_core_ledger` adds isolation columns, global position, integrity hashes, identity tables, projections, checkpoints.
- Append-only SQL triggers reject `UPDATE`/`DELETE`/`TRUNCATE` on `engine_events` and `audit_records`.
- `projection_checkpoints`: `UPDATE` allowed (derived state); `DELETE`/`TRUNCATE` rejected.
- Governance events live in `engine_events` (no separate `governance_events` table).
- Roles created: `engine_migrator`, `engine_runtime`, `engine_readonly` (passwords set out of band; never hardcoded).
- Runtime: `SELECT`+`INSERT` on ledger; no `UPDATE`/`DELETE`/`TRUNCATE` on ledger.

## Identity, authentication, scopes, isolation

- Canonical frozen identities: `ApplicationIdentity`, `UserIdentity`, `ActorIdentity`, `ServiceIdentity`, `TenantIdentity`.
- API credentials: public `cred_*` id, secret `imx_sk_*` shown once, SHA-256 hash only at rest.
- Request auth: `Authorization: Bearer <secret>`; scopes loaded from the application row (token cannot elevate itself).
- Effective actor always from auth context; body cannot spoof `actor_id` / `owner_id`.
- Enforced scopes include `SUBMIT_OBSERVATION`, `READ_AUDIT`, `READ_INTELLIGENCE`, `ADMINISTER_ENGINE`, plus the full Stage 1 vocabulary.
- Isolation by `tenant_id` / `owner_id` / `application_id` / `domain_pack` on material rows.
- Admin only via local CLI (`python -m intelligence_maxxxing.cli ...`); no public HTTP admin endpoints.

## Event catalog, append-only, concurrency

- Versioned catalog in `contracts/events/catalog.py` validates `event_type` + `schema_version` → payload.
- `ObservationAccepted` 1.0 remains backward compatible with Stage 0.
- Event store v2: `append_one` / `append_batch`, streams, owner-scoped reads, optimistic concurrency, monotonic `global_position`.
- Composite idempotency scope: `(application_id, owner_id, action, idempotency_key)`.
- Concurrent same payload → one result for all callers; concurrent different payload → deterministic `409 IDEMPOTENCY_CONFLICT` (never raw IntegrityError / HTTP 500).

## Projections and integrity

- Projection `accepted_observations` derived exclusively from `engine_events`, disposable and rebuildable.
- Checkpoints are mutable derived state (documented append-only exception); rebuild history is append-only.
- Unknown projector event types STOP and mark checkpoint `QUARANTINED`.
- Integrity chain per `(owner_id, application_id)` stream with `previous_event_hash` / `event_hash`.
- Full verification emits `IntegrityCheckCompleted`; violations emit `IntegrityViolationDetected` and invoke the kill-switch hook.

## Health snapshot fix and migration safety

- Audits persist a measured `HealthSnapshot` from `HealthSnapshotProvider` (never a hardcoded healthy literal).
- Unchecked components are `NOT_CHECKED`, never `HEALTHY`.
- Endpoints: `GET /health/live`, `GET /health/ready`, authenticated `GET /api/v1/health`.
- `MigrationSafetyPolicy` + `scripts/db/safe_downgrade.ps1` block destructive downgrades unless all flags, backup id, admin actor and confirm phrase are present.

## Endpoints and SDK

Kept:

- `POST /api/v1/observations` (requires `SUBMIT_OBSERVATION`)
- `GET /api/v1/audits/{audit_id}` (requires `READ_AUDIT`)
- `GET /api/v1/health` (authenticated detail)

Added:

- `GET /api/v1/observations/{observation_id}`
- `GET /api/v1/observations` (cursor pagination, projection freshness)
- `GET /health/live`, `GET /health/ready`

SDK v2 (`intelligence_maxxxing_client`): Bearer credential, `health` / `live` / `ready` / `submit_observation` / `get_observation` / `list_observations` / `get_audit`, typed 401/403/404/409/503. Never imports Core.

## Tests

| Suite | Result |
| --- | --- |
| Stage 0 suite retained + Stage 1 unit/integration/contract/constitutional | **PASS** — 104 tests (`pytest -m "not postgres"`) |
| PostgreSQL gates (`tests/postgres`) | **PASS** — 13 tests against real PostgreSQL 16.14 |
| Constitution manifest | **PASS** (byte-identical frozen docs) |

Mandatory named protections covered include append-only SQL role tests, concurrent idempotency, identity/auth reject paths, permission allow/deny, event catalog, integrity, projections, health snapshots, and migration safety.

## Quality gates

| Gate | Result |
| --- | --- |
| Ruff lint / format | PASS |
| mypy (`src` + `sdk`) | PASS |
| import-linter | PASS (5 contracts kept) |
| pytest (non-postgres) | PASS |
| verify_constitution.ps1 | PASS |
| run_quality_gates.ps1 | PASS |
| run_postgres_gates.ps1 | PASS |

## CI

GitHub Actions workflow `.github/workflows/ci.yml`:

- Python 3.12 clean install
- Ruff, format, mypy, import-linter, constitution manifest, pytest
- PostgreSQL 16 service, Alembic from zero, postgres marker suite

## Benchmarks (local SQLite measurement, not a hard gate)

```text
submit_observation_p50_ms=26.86
submit_observation_p95_ms=120.20
list_observations_p50_ms=16.09
list_observations_p95_ms=20.91
replay_events_scanned=1006
projection_rebuild_ms=582.62
integrity_events_checked=1007
integrity_check_ms=140.75
concurrent_idempotency_ms=242.96
concurrent_idempotency_statuses=[200, 200, 200, 200, 200, 200, 200, 201]
```

No absurd performance gates were fixed; these are regression baselines.

## Warnings

1. Signed short-lived tokens were deferred: Bearer API secrets over a private loopback interface are used instead (documented in `IDENTITY_AND_PERMISSION_MODEL.md`).
2. Rate limiting is a port/hook with a no-op default (contract only).
3. Integrity chain is tamper/corruption **detection**, not absolute cryptographic security against a writer who can rewrite whole streams.
4. Suggested five-way commit split was partially combined because the change set is tightly coupled around migration `0002`.

## Technical debt

- Automatic incremental projection catch-up worker (currently inline upsert + explicit rebuild CLI).
- Credential last-used updates are best-effort per request; high-traffic counters may want batching.
- SQLite migration path rebuilds `engine_events` for hermetic tests; production path is PostgreSQL-only for append-only triggers/roles.
- `engine_runtime` passwords must be operated out of band (by design).

## Rule status summary

| Area | Status |
| --- | --- |
| Identity / auth / scopes / isolation | **IMPLEMENTED** |
| Append-only SQL + roles | **IMPLEMENTED** |
| Concurrent composite idempotency | **IMPLEMENTED** |
| Event catalog + integrity chain | **IMPLEMENTED** |
| Rebuildable `accepted_observations` | **IMPLEMENTED** |
| Measured health snapshots | **IMPLEMENTED** |
| Migration safety policy | **IMPLEMENTED** |
| Rate-limit enforcement | **CONTRACT_ONLY** (hook present) |
| Belief Engine / Domain Pack logic / LifeMaxxxing | **DEFERRED** |

## Exact start command

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\start_postgres.ps1
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
python -m intelligence_maxxxing.cli bootstrap-owner --tenant-name "Private" --owner-name "Owner"
python -m intelligence_maxxxing.cli register-application --display-name "dev-app" --owner-id <owner_id>
python -m intelligence_maxxxing.cli create-credential --application-id <application_id>
python -m intelligence_maxxxing.cli grant-scope --application-id <application_id> --scope SUBMIT_OBSERVATION
python -m intelligence_maxxxing.cli grant-scope --application-id <application_id> --scope READ_AUDIT
python -m intelligence_maxxxing.cli grant-scope --application-id <application_id> --scope READ_INTELLIGENCE
powershell -ExecutionPolicy Bypass -File scripts\dev\run_engine.ps1
```

Local URL: `http://127.0.0.1:8100`

Public probes: `http://127.0.0.1:8100/health/live`, `http://127.0.0.1:8100/health/ready`

Authenticated API base: `http://127.0.0.1:8100/api/v1`

## Next recommended stage

Stage 2 candidates (not started):

1. LifeMaxxxing as the first external client against this trusted ledger (observations + audits only).
2. Decision Loop / Belief Engine behind the same auth, isolation and append-only guarantees.
3. Real rate limiting and optional short-lived signed tokens if the Engine leaves private loopback.

Do not integrate LifeMaxxxing inside the Core. Applications remain external HTTP/SDK clients.
