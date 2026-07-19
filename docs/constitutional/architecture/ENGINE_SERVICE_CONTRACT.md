# ENGINE SERVICE CONTRACT

**Status:** Binding application boundary  
**Version:** 1.0  
**Working backend:** IntelligenceMaxxxing Engine  
**Parent authority:** Constitution v1.1

---

## 1. Foundational boundary

The Engine is an independent backend.

Applications never call internal modules and never read Engine databases directly.

All communication uses public, versioned, authenticated contracts.

Applications remain separate products:

- LifeMaxxxing;
- TradingMaxxxing;
- Betting Bot;
- future applications.

Each keeps its own frontend, user experience, and local operational features.

---

## 2. Sources of truth

### Engine owns

- accepted observations;
- evidence lineage;
- hypotheses;
- experiments;
- beliefs;
- recommendations;
- decision records;
- outcomes;
- learning;
- permissions;
- audit;
- Domain Pack health.

### Applications own

- frontend state;
- navigation;
- local-only features;
- presentation;
- offline queue;
- cached responses;
- application-specific operational state not promoted to Engine knowledge.

---

## 3. Adapter model

Each application has an adapter:

- `LifeMaxxxingAdapter`
- `TradingMaxxxingAdapter`
- `BettingBotAdapter`

The Engine repository owns:

- public API specification;
- event schemas;
- SDK interfaces;
- compatibility fixtures;
- contract tests.

Each application repository owns:

- application-specific adapter implementation;
- local queue;
- cache;
- UI mapping;
- sync behavior.

Compatibility tests run on both sides.

---

## 4. Communication styles

### 4.1 Synchronous API

Used for:

- current recommendation;
- current belief;
- health check;
- audit summary;
- permission check;
- status lookup.

Initial protocol: REST over HTTPS.

### 4.2 Asynchronous jobs

Used for:

- simulations;
- historical analysis;
- backtests;
- hypothesis generation;
- experiment evaluation;
- large reports.

Jobs must support:

- idempotent submission;
- status polling;
- cancellation;
- pause and resume when supported;
- progress;
- resource limits.

### 4.3 Application events

Examples:

- `WorkoutCompleted`
- `SleepRecorded`
- `DecisionTaken`
- `TradeClosed`
- `BetResolved`

### 4.4 Engine events

Examples:

- `BeliefUpdated`
- `RecommendationReady`
- `RiskDetected`
- `ExperimentCompleted`
- `HumanReviewRequired`
- `MethodDegraded`

Initial implementation uses REST plus internal durable events. gRPC is deferred.

---

## 5. Permission scopes

Minimum scopes:

- `READ_INTELLIGENCE`
- `SUBMIT_EVIDENCE`
- `EXECUTE_ACTION`

Additional recommended scopes:

- `READ_AUDIT`
- `SUBMIT_DECISION`
- `SUBMIT_OUTCOME`
- `REQUEST_DELETION`
- `MANAGE_DOMAIN_PACK`
- `APPROVE_EXECUTION`

Permissions are constrained by:

- application;
- user;
- Domain Pack;
- object type;
- action;
- maximum impact or amount;
- duration;
- environment.

---

## 6. Mutation rules

Applications may:

- submit observations;
- submit supporting evidence;
- register human decisions;
- register outcomes;
- request actions;
- request governed archive or deletion.

Applications may not:

- modify beliefs directly;
- rewrite conclusions;
- change experiment results;
- edit audit history;
- delete Engine objects directly;
- promote methods;
- bypass Domain Pack validation.

New evidence may cause the Engine to produce a new version of a belief. It never mutates history invisibly.

---

## 7. API versioning

Base path:

```text
/api/v1/
```

Separate versions exist for:

- API contract;
- core schemas;
- Domain Pack schemas;
- event schemas;
- SDK.

No breaking change is allowed within the same major version.

A deprecated major version remains supported for at least 30 days during the private single-user phase. Before external or multiuser use, the minimum window must be reviewed and is expected to increase.

Deprecation requires:

- announcement;
- replacement contract;
- migration guide;
- telemetry of remaining clients;
- final removal date.

---

## 8. Response envelope

Every response includes:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "req_...",
    "engine_version": "0.x",
    "api_version": "v1",
    "domain_pack": "life",
    "domain_pack_version": "0.x",
    "generated_at": "ISO-8601",
    "freshness": {},
    "confidence": {},
    "health": {},
    "audit_id": "audit_..."
  }
}
```

Recommendations include:

- concise explanation;
- confidence summary;
- known limitations;
- required human action;
- audit ID.

Detail levels:

- `summary`
- `standard`
- `full_audit`

---

## 9. Offline-first application behavior

When the Engine is unavailable, applications:

- keep local features working;
- display the last valid result;
- mark it `STALE`;
- never invent new intelligence;
- queue observations and outcomes locally;
- synchronize later using idempotency keys;
- block critical execution;
- avoid duplicate jobs.

The frontend queue must preserve:

- local event ID;
- created time;
- user;
- schema version;
- retry count;
- sync state;
- conflict state.

---

## 10. Authentication and authorization

Initial authentication combines:

- private network where available;
- application API credentials;
- signed short-lived tokens;
- user authorization.

Execution tokens must be specific to:

- app;
- user;
- action;
- Domain Pack;
- maximum impact;
- expiry.

Secrets never live in frontend source code or Domain Packs.

---

## 11. Idempotency

Every write endpoint and job submission accepts an idempotency key.

The Engine must return the original result when the same authorized request is safely retried.

Duplicate prevention applies to:

- observations;
- decisions;
- outcomes;
- job submissions;
- execution requests;
- offline sync.

---

## 12. Initial public endpoint families

```text
GET  /api/v1/health
POST /api/v1/observations
POST /api/v1/evidence
POST /api/v1/hypotheses
POST /api/v1/experiments
GET  /api/v1/jobs/{job_id}
POST /api/v1/recommendations/query
POST /api/v1/decisions
POST /api/v1/outcomes
GET  /api/v1/beliefs/{belief_id}
GET  /api/v1/audits/{audit_id}
POST /api/v1/actions/prepare
POST /api/v1/actions/execute
POST /api/v1/governance/deletion-requests
```

Implementation may begin with a smaller subset, but semantics must remain consistent.

---

## 13. Contract tests

- `APP_CANNOT_IMPORT_CORE`
- `APP_CANNOT_READ_ENGINE_DB`
- `APP_CANNOT_MUTATE_BELIEF`
- `WRITE_REQUIRES_IDEMPOTENCY`
- `EXECUTION_REQUIRES_SCOPED_TOKEN`
- `OFFLINE_QUEUE_REPLAYS_ONCE`
- `STALE_RESULT_MARKED`
- `BREAKING_CHANGE_REQUIRES_MAJOR_VERSION`
- `RECOMMENDATION_HAS_AUDIT_ID`
- `DOMAIN_ISOLATION_ENFORCED`

---
