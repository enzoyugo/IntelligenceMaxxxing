# STAGE 1.1 — Isolation, Integrity Concurrency and Safe Projections Report

## Executive verdict

```text
STAGE_1_1_ISOLATION_INTEGRITY_HARDENING_PASS
```

Stage 1 shipped a working trusted core ledger, but an independent adversarial audit
provisionally downgraded it to `STAGE_1_TRUSTED_CORE_LEDGER_FAIL /
TARGETED_HARDENING_REQUIRED_BEFORE_STAGE_2`. This report does **not** rewrite the Stage 1
report to hide those findings. It records each confirmed defect and how Stage 1.1
corrected it, verified on real PostgreSQL 16.

---

## 1. Defects found and how they were fixed

### D1 — Audits isolated by owner but not by application (existence leak)

**Confirmed:** `get_by_audit_id(owner_id, audit_id)` and `list_by_audit(owner_id, audit_id)`
let App B read App A's audit when both shared an owner.

**Fix:** every audit read is scoped by `(tenant_id, owner_id, application_id, audit_id)`.
Out-of-scope ids behave as **missing → HTTP 404**, never 403, so existence is not leaked
across applications or tenants.
`AuditStorePort.get_by_audit_id`, `SqlAlchemyAuditStore`, `EventStorePort.list_by_audit`,
`SqlAlchemyEventStore.list_by_audit`, and `GetAuditUseCase` all carry the full triple.

**Regression:** `tests/integration/test_audit_isolation.py` +
`test_stage1_1_hardening.py::test_cross_application_audit_exploit_regression` (SQLite **and**
real PostgreSQL): App A and App B under the same owner; App B → App A audit == **404**.

### D2 — Integrity chain forks under concurrency

**Confirmed:** read-latest-hash → compute → insert allowed two concurrent same-stream
writers to reuse one `previous_event_hash` and fork the chain.

**Fix:** a transactional stream head (`event_stream_heads`, PK
`(tenant_id, owner_id, application_id)`) is created race-safe
(`INSERT ... ON CONFLICT DO NOTHING`), locked `SELECT ... FOR UPDATE`, and used as the
anchor for the next hash — insert and head-advance commit atomically. `append_batch` groups
by stream and locks in deterministic key order to avoid deadlocks. See
`docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md`.

**Proof (real PostgreSQL):** `CONCURRENT_DISTINCT_EVENTS_SAME_STREAM_FORM_ONE_CHAIN` launches
20 concurrent writers on one stream → 20 events written, chain valid, one head, head hash ==
last event hash. Plus `STREAM_HEAD_UPDATE_IS_ATOMIC`, `FAILED_APPEND_DOES_NOT_ADVANCE_STREAM_HEAD`,
`APPEND_BATCH_CHAINS_IN_INPUT_ORDER`, `CONCURRENT_EVENTS_DIFFERENT_STREAMS_DO_NOT_BLOCK_GLOBALLY`.

### D3 — Incremental integrity verification invalid

**Confirmed:** `verify_chain()` always started with `previous_hash = None`, so an incremental
range starting mid-stream flagged its first (legitimate) event as corruption.

**Fix:** `verify_chain(events, initial_previous_hash=...)` accepts a trusted anchor.
`integrity_checkpoints` stores the last reliably verified position/event/hash per stream;
INCREMENTAL resumes after the checkpoint using `last_verified_hash` as the anchor and
advances the checkpoint **only on success**. Without a checkpoint it falls back to FULL.

**Proof:** `tests/unit/test_integrity_incremental.py` — anchor accepted, new tampering
detected, checkpoint not advanced on failure, FULL and INCREMENTAL agree; plus
`test_full_and_incremental_agree` on real PostgreSQL.

### D4 — Integrity violation hook did not block writes

**Confirmed:** `LoggingIntegrityViolationHook` only logged; a corrupted stream kept accepting
writes.

**Fix:** a detected break sets `status = QUARANTINED` on the stream head (with `reason`,
`broken_event_id`, `detected_at`, `quarantine_audit_id`) and emits `IntegrityViolationDetected`
+ `IntegrityStreamQuarantined`. Every subsequent append to that stream raises
`StreamQuarantinedError` → **HTTP 409**. Release is CLI-only (`inspect-stream`, `verify-stream`,
`unquarantine-stream`), requires `ADMINISTER_ENGINE` **and** a successful FULL verify, and emits
`IntegrityStreamReleased`.

**Proof:** `tests/integration/test_quarantine.py` — violation quarantines, quarantined stream
blocks writes (409), other streams stay available, unquarantine requires admin + successful
full verify, quarantine action is audited; plus `QUARANTINED_STREAM_REJECTS_APPEND` on real
PostgreSQL.

### D5 — Projection `verify()` mutated the live projection

**Confirmed:** `verify()` called `rebuild(from_scratch=True)`, destructively rebuilding the
active projection.

**Fix:** `verify`, `rebuild`, and `promote` are separated. `verify` replays into
`accepted_observations_shadow`, checksums it, and compares to live **without touching live**.
`rebuild(from_scratch=True)` builds the shadow, validates, then **atomically promotes**
(same transaction) into live. An unknown event quarantines the shadow reconstruction, leaves
live intact, and never leaves a half-empty table.

**Proof:** `tests/integration/test_shadow_projection.py` — verify does not mutate live, verify
failure preserves live, unknown event does not empty live, shadow checksum matches live,
promotion is atomic, failed promotion rolls back, reads continue during verify; plus
`SHADOW_PROJECTION_VERIFY_ON_POSTGRES`.

### D6 — Aggregate concurrency not scoped by tenant/owner/application

**Confirmed:** the aggregate unique constraint and `get_latest_aggregate_version()` used only
`(aggregate_type, aggregate_id, aggregate_version)`.

**Fix:** aggregate identity is now `(tenant_id, owner_id, application_id, aggregate_type,
aggregate_id, aggregate_version)` — constraint, ORM, migration 0003, `EventStorePort`,
`get_latest_aggregate_version`, `list_by_aggregate`, and all callers.

**Proof:** `tests/unit/test_aggregate_scope.py` — same aggregate id allowed across different
applications and owners; same version in the same scope rejected; lookups never cross an
application.

---

## 2. Baseline and commits

| Item | Value |
| --- | --- |
| Stage 1 final reference | `8f87730` — `STAGE_1_REPORT: clarify push status wording` |
| Stage 1.1 baseline | `54ce3d3` — `STAGE_1_1_BASELINE: freeze Stage 1 before adversarial hardening` |
| Isolation | `3cb5ee4` — `STAGE_1_1_ISOLATION: application-scoped audits and aggregates` |
| Integrity | `360aca2` — `STAGE_1_1_INTEGRITY: concurrent chain heads, checkpoints and quarantine` |
| Projections | `79831ae` — `STAGE_1_1_PROJECTIONS: non-destructive shadow verification` |
| Report | `STAGE_1_1_REPORT: adversarial validation and final report` (this commit) |
| Canonical branch | `main` |
| Remote | `origin` |

---

## 3. PostgreSQL verification

| Item | Value |
| --- | --- |
| Verification | **REAL POSTGRESQL 16 ALPINE** (no SQLite fallback) |
| Exact version | PostgreSQL 16.14 |
| Method | Docker Compose service `postgres` (`postgres:16-alpine`), `127.0.0.1:5432` |
| Migration path | `0001 → 0002 → 0003` applied from an empty schema |
| Gate script | `scripts/audit/run_postgres_gates.ps1` (extended with Stage 1.1 concurrency gates) |
| CI | `.github/workflows/ci.yml` runs the Stage 1.1 multi-session gates on PostgreSQL |

---

## 4. Tests

| Item | Value |
| --- | --- |
| Existing non-PostgreSQL tests retained | 104 (all still passing) |
| Total non-PostgreSQL tests now | 132 (+28 new) |
| Existing PostgreSQL tests retained | 13 (all still passing) |
| Total PostgreSQL tests now | 23 (+10 new) |
| Coverage reduction | none (no assertions removed) |

New suites: `tests/integration/test_audit_isolation.py`, `tests/unit/test_aggregate_scope.py`,
`tests/unit/test_integrity_incremental.py`, `tests/integration/test_quarantine.py`,
`tests/integration/test_shadow_projection.py`, `tests/postgres/test_stage1_1_hardening.py`.

---

## 5. Migration 0003

`0003_stage1_1_integrity_isolation_hardening` creates `event_stream_heads`,
`integrity_checkpoints`, and `accepted_observations_shadow`; replaces the aggregate unique
constraint with the tenant/owner/application-scoped one; adds indices; and on PostgreSQL
installs DELETE/TRUNCATE-blocking (UPDATE-allowed) triggers on the two new control tables and
grants the runtime role the governed head/checkpoint UPDATE. Hashes of `0001` and `0002` are
untouched. Upgrade `0001 → 0002 → 0003` verified from zero on PostgreSQL 16.

---

## 6. Quality gates

| Gate | Result |
|---|---|
| `ruff check .` | PASS |
| `ruff format --check .` | PASS |
| `mypy src sdk` | PASS |
| `pytest -q` (non-PostgreSQL) | PASS (132) |
| `lint-imports` | PASS (5 contracts kept) |
| `verify_constitution.ps1` | PASS (constitution byte-identical) |
| `run_quality_gates.ps1` | PASS |
| `run_postgres_gates.ps1` | PASS (23 PostgreSQL tests) |

---

## 7. Warnings

- Cross-process chain and quarantine guarantees are proven on **real PostgreSQL only**.
  SQLite is used for hermetic behavior tests and is never presented as equivalent for the
  concurrency guarantee.
- Integrity verification and quarantine remain **operator/CLI-triggered**; there is no
  automatic background verifier or scheduler in Stage 1.1 (out of scope).
- Quarantine release still trusts a local operator holding `ADMINISTER_ENGINE`; remote
  deployment hardening (RBAC, secret manager, encryption at rest) remains deferred.

---

## 8. Next recommended stage

Only after these hardening gates pass:

```text
STAGE 2 — LIFEMAXXXING EXTERNAL CLIENT INTEGRATION
```

LifeMaxxxing was **not** connected in this sprint.
