# IntelligenceMaxxxing Engine

Constitutionally governed, application-agnostic intelligence backend.

## What it is

IntelligenceMaxxxing is an **independent backend service** that will act as the
source of truth for accepted observations, evidence, hypotheses, experiments,
beliefs, recommendations, recorded decisions, outcomes, learning, permissions
and audit — for every client application (LifeMaxxxing, TradingMaxxxing, the
betting bot, and future apps).

Stage 0 (current) delivers the constitutional foundation as a real, running,
tested backend: a versioned public API, strict canonical schemas, an
append-only event store, a recoverable audit trail, and idempotent writes.

## What it is not

- Not a frontend, and it never will contain one.
- Not an AI agent: there is **no** LLM, belief engine, hypothesis generation,
  recommendation logic, trading or betting capability in Stage 0. Contracts
  for those exist; nothing simulates that they work.
- Not integrated with LifeMaxxxing/TradingMaxxxing yet (LifeMaxxxing will be
  the first integration, in a later stage).

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

## Architecture (Stage 0)

Layered modular monolith with boundaries enforced by import-linter **and**
constitutional tests:

```text
api            -> translates HTTP to use cases (no domain logic, no table access)
application    -> use cases + ports (no FastAPI, no SQLAlchemy)
domain         -> pure Python canonical objects (no web, no ORM, no network)
infrastructure -> SQLAlchemy/PostgreSQL implementations of the ports
contracts      -> public versioned schemas (never ORM models)
domain_packs   -> contract-only placeholders (life, trading, sports_betting)
sdk/python     -> public client; consumes HTTP only, never imports the Core
```

The smoke path proven by tests and live checks:

```text
Application -> Public API -> Observation validation -> Append-only event
            -> Audit record -> Versioned response envelope
```

## Install

```powershell
cd E:\IntelligenceMaxxxing
python -m pip install -e ".[dev]"
# or: powershell -ExecutionPolicy Bypass -File scripts\dev\setup_engine.ps1
```

## Run PostgreSQL (Docker)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\start_postgres.ps1
```

## Migrate

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
# or: python -m alembic upgrade head
```

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

Health:

```powershell
curl.exe http://127.0.0.1:8100/api/v1/health
```

Submit an observation (mandatory `Idempotency-Key`):

```powershell
curl.exe -X POST http://127.0.0.1:8100/api/v1/observations `
  -H "Content-Type: application/json" `
  -H "Idempotency-Key: demo-001" `
  -d '{\"schema_version\":\"1.0\",\"subject\":\"sleep\",\"statement\":\"Slept 7.5 hours\",\"knowledge_class\":\"OBSERVED_FACT\",\"observed_by\":\"demo\",\"context\":{\"scope\":\"personal\"}}'
```

Retrieve the audit (use the `audit_id` returned above):

```powershell
curl.exe http://127.0.0.1:8100/api/v1/audits/aud_...
```

Or use the public SDK (which never imports the Core):

```python
from intelligence_maxxxing_client import IntelligenceMaxxxingClient

with IntelligenceMaxxxingClient(base_url="http://127.0.0.1:8100") as client:
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

## Implemented in Stage 0

- Public API v1: `GET /api/v1/health`, `POST /api/v1/observations`,
  `GET /api/v1/audits/{audit_id}` with a consistent response envelope.
- Canonical schemas v1 (strict, frozen, versioned) for all core objects.
- Append-only event store (`engine_events`) with no update/delete surface.
- Recoverable audit trail (`audit_records`).
- Idempotency: safe retries, explicit 409 conflicts, DB-level uniqueness.
- Initial Alembic migration; PostgreSQL as the central database (SQLite for
  tests only).
- Constitutional test suite + import boundaries + schema snapshots.
- Structured JSON logging; honest component health checks.
- Public Python SDK.

## Explicitly out of scope (Stage 0)

Frontend/console, LifeMaxxxing/TradingMaxxxing/betting integrations, real
Domain Pack logic, hypothesis generation, Belief Engine, Cross-Domain
Coordinator, knowledge graph, vector DB, LLMs, trading/bet execution,
microservices, cloud deployment, active autonomy, real recommendations.

**LifeMaxxxing will be the first future integration** (Stage 3 per
`TECHNICAL_ARCHITECTURE.md` §14).

## Further reading

- `docs/architecture/CONSTITUTION_TRACEABILITY_MATRIX.md` — principle → code → test mapping.
- `docs/architecture/OFFLINE_SYNC_CONTRACT.md` — offline/sync contract.
- `docs/runbooks/LOCAL_DEVELOPMENT.md` — day-to-day commands.
- `docs/reviews/` — sprint reports and conflict records.
