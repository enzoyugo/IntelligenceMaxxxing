# TECHNICAL ARCHITECTURE

**Status:** Foundational architecture  
**Version:** 1.0  
**Repository working name:** `IntelligenceMaxxxing`  
**Product name:** Provisional  
**Internal language:** English  
**Foundation documentation:** Spanish, with future official English translation

---

## 1. Architectural thesis

IntelligenceMaxxxing is an independent backend service consumed by multiple applications.

It starts as a modular monolith, not as embedded code and not as premature microservices.

The initial deployment unit is one codebase with strict module boundaries, plus separate process types for API and long-running workers.

---

## 2. Non-negotiable boundaries

- No application imports Core modules.
- No application reads Engine databases.
- No Domain Pack owns universal knowledge objects.
- No LLM directly updates beliefs.
- No frontend technology affects Core design.
- No provider is part of the Engine's identity.
- No active method bypasses governance.
- No current conclusion overwrites historical evidence.

---

## 3. Initial technology choices

### Core

- Python
- FastAPI
- Pydantic schemas
- SQLAlchemy or equivalent explicit data access layer
- PostgreSQL central database
- Docker-compatible deployment
- OpenAPI-generated public contract

### Async processing

Initial architecture supports:

- durable job queue;
- separate worker process;
- scheduled jobs;
- idempotent execution;
- resource quotas;
- cancellation and recovery.

The exact queue technology is replaceable and must remain behind an internal interface.

### Storage

- PostgreSQL: structured state, metadata, permissions, materialized views.
- Append-only event log: history of observations, decisions, outcomes, belief changes, and governance events.
- Object storage: datasets, reports, large artifacts.
- Local SQLite: tests, edge/offline prototypes, and application queues only.
- Vector index: added only for a demonstrated retrieval use case.
- Knowledge graph: deferred until relationships cannot be represented adequately with relational and event models.

---

## 4. Modular monolith structure

```text
IntelligenceMaxxxing/
├── docs/
│   ├── foundation/
│   └── architecture/
├── src/
│   └── intelligence_maxxxing/
│       ├── api/
│       ├── identity/
│       ├── observations/
│       ├── evidence/
│       ├── hypotheses/
│       ├── experiments/
│       ├── beliefs/
│       ├── recommendations/
│       ├── decisions/
│       ├── outcomes/
│       ├── learning/
│       ├── memory/
│       ├── governance/
│       ├── permissions/
│       ├── audit/
│       ├── jobs/
│       ├── events/
│       ├── cross_domain/
│       └── domain_packs/
│           ├── life/
│           ├── trading/
│           └── sports_betting/
├── sdk/
├── schemas/
├── migrations/
├── tests/
├── fixtures/
├── scripts/
├── reports/
├── Dockerfile
└── pyproject.toml
```

Module rules are enforced with import-boundary tests.

---

## 5. Runtime topology

### API process

Responsibilities:

- authentication;
- validation;
- synchronous queries;
- job submission;
- health;
- audit retrieval;
- permission enforcement.

### Worker process

Responsibilities:

- simulations;
- experiments;
- hypothesis generation;
- evidence evaluation;
- report generation;
- belief recalibration;
- background synchronization.

### Scheduler

Responsibilities:

- periodic self-evaluation;
- stale-data checks;
- calibration monitoring;
- backups;
- Domain Pack health;
- governance reports.

### Database

Central PostgreSQL with logically isolated schemas or equivalent boundaries for:

- Core;
- personal memory;
- universal memory;
- Domain Packs;
- audit;
- governance.

---

## 6. Render-compatible deployment

Render is a viable initial deployment target because the architecture can map to:

- a web service for FastAPI;
- a background worker for long-running jobs;
- scheduled jobs;
- managed PostgreSQL.

The architecture is not Render-dependent.

Production assumptions:

- durable data must live in managed PostgreSQL or durable object storage;
- the service filesystem is treated as ephemeral by default;
- free resources are development-only;
- an always-on durable deployment is expected to use paid resources;
- persistent local disk is not used as a shared database or shared cross-service filesystem;
- external provider limits must never become Core semantics.

A local/private deployment remains supported through Docker and secure networking.

---

## 7. Local-first and cloud hybrid

### Life data

LifeMaxxxing retains local-first behavior for sensitive capture and offline use.

It sends only authorized data to the Engine.

### Private Engine

The initial Engine is single-user but designed with explicit `user_id`, `tenant_id`, and ownership boundaries to avoid a future rewrite.

### Connectivity

Supported modes:

- cloud Engine over HTTPS;
- local Engine through private VPN;
- hybrid sync for sensitive or high-volume data.

The Engine continues scheduled and background work when applications are closed.

---

## 8. Data model principles

### Event-first history

Material events are append-only:

- observation accepted;
- evidence attached;
- hypothesis created;
- experiment started/completed;
- recommendation issued;
- decision recorded;
- outcome recorded;
- belief updated;
- method promoted/degraded;
- permission changed.

### Materialized current state

Current beliefs and recommendations are projections derived from event history.

They may be rebuilt.

### Object identity

Every object uses stable IDs and versions.

Recommended prefixes:

- `obs_`
- `evd_`
- `hyp_`
- `exp_`
- `blf_`
- `rec_`
- `dec_`
- `out_`
- `lrn_`
- `aud_`
- `job_`

---

## 9. Security architecture

### Authentication

Combination of:

- HTTPS;
- private network where available;
- application credentials;
- signed short-lived tokens;
- user authorization.

### Authorization

RBAC plus scoped permissions by:

- app;
- user;
- Domain Pack;
- action;
- data class;
- autonomy level.

### Data protection

- encryption in transit;
- encryption at rest;
- secret manager for credentials;
- no credentials inside Domain Packs;
- audit of sensitive reads;
- strong separation between personal, universal, and domain memory.

### Privacy

A LifeMaxxxing client cannot read TradingMaxxxing evidence unless explicitly authorized.

Cross-domain coordination operates on authorized published impacts, not unrestricted raw data.

---

## 10. Reliability

### Failure behavior

When unavailable:

- apps show cached state as stale;
- apps queue events;
- critical execution is blocked;
- retries are idempotent;
- local features continue.

### Recovery

Initial priority is reliable recovery, not high availability.

Minimum operational requirements:

- automatic process restart;
- health checks;
- database backup;
- restore test;
- structured logs;
- dead-letter handling;
- job replay protection.

### Backup policy

Initial full backup cadence: weekly.

Because append-only events may be more valuable than a one-week loss window, production design should also include more frequent database-native or incremental protection when the first real data is ingested.

Final RPO and RTO are set before production activation.

### Resource isolation

Long research jobs cannot starve the API.

Controls include:

- separate worker;
- queue limits;
- concurrency limits;
- memory and CPU budgets;
- job priorities;
- cancellation;
- maximum run time.

---

## 11. AI provider abstraction

The Core is provider-independent.

LLMs may:

- generate hypotheses;
- translate natural language;
- explain evidence;
- suggest experiment plans;
- detect possible relationships.

LLMs are never final evidence and never update beliefs directly.

Every model output records:

- provider;
- model;
- prompt;
- parameters;
- model version;
- evidence context;
- timestamp;
- purpose;
- resulting proposal ID.

Personal information prioritizes local models where practical.

---

## 12. Integration sequence

### First — LifeMaxxxing

Reason:

- proves the Engine can handle human values, subjective data, uncertainty, offline sync, and multiobjective decisions;
- avoids merely duplicating TradingMaxxxing's existing research machinery.

Initial mode: read-only intelligence and evidence submission.

### Second — TradingMaxxxing

Reason:

- validates structured evidence, experimentation, calibration, and high-rigor audit;
- integrates with the existing research engine rather than replacing it.

Initial mode: read-only adapter and imported evidence summaries.

### Third — Betting Bot

Reason:

- tests high randomness, sports evidence, confidence calibration, and bankroll/risk concepts after the universal loop is stable.

---

## 13. First vertical slice

The first complete loop must:

1. accept an observation from LifeMaxxxing;
2. validate and classify it;
3. register or generate a hypothesis;
4. attach evidence;
5. create a calibrated belief;
6. issue an explained recommendation;
7. record the human decision;
8. receive the outcome;
9. separate decision quality from outcome;
10. create learning;
11. update the belief;
12. expose a full audit.

No UI redesign is required to prove this slice.

---

## 14. Initial delivery stages

### Stage 0 — Foundation

- freeze documents;
- create repository;
- define schemas;
- add constitutional tests.

### Stage 1 — Core ledger

- identity;
- append-only events;
- observations;
- audit;
- permissions.

### Stage 2 — Decision loop

- hypotheses;
- evidence;
- beliefs;
- recommendations;
- decisions;
- outcomes;
- learning.

### Stage 3 — Life adapter

- offline queue;
- observation ingest;
- recommendation query;
- decision and outcome feedback.

### Stage 4 — Worker and scheduling

- async jobs;
- self-evaluation;
- calibration;
- health.

### Stage 5 — Trading adapter

- evidence import;
- experiment references;
- belief comparison;
- no replacement of TradingMaxxxing research engine.

---

## 15. Architecture tests

- `CORE_HAS_NO_APPLICATION_IMPORTS`
- `APPLICATIONS_USE_PUBLIC_CONTRACT_ONLY`
- `DOMAIN_PACK_HAS_NO_DIRECT_DB_ACCESS_OUTSIDE_REPOSITORY`
- `EVENTS_APPEND_ONLY`
- `PROJECTIONS_REBUILD_FROM_EVENTS`
- `LLM_CANNOT_WRITE_BELIEF`
- `WORKER_RESOURCE_LIMITED`
- `OFFLINE_SYNC_IDEMPOTENT`
- `SENSITIVE_READ_AUDITED`
- `PROVIDER_REPLACEABLE`
- `LIFE_FIRST_VERTICAL_SLICE_COMPLETE`

---
