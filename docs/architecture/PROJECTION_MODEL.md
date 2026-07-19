# Projection Model — Stage 1

**Status:** IMPLEMENTED (Stage 1)  
**Authority:** Technical Architecture §8, Engine Service Contract §4  
**Code:** `application/use_cases/projections.py`, `infrastructure/repositories/projections.py`

---

## 1. Purpose

Projections are **derived, disposable, rebuildable** read models. The append-only `engine_events` ledger is the sole source of truth. Projections exist for query performance and API convenience only.

Stage 1 implements one projection: **`accepted_observations`** (version `1.0`).

---

## 2. accepted_observations

| Property | Value |
|---|---|
| Table | `accepted_observations` |
| Source | `ObservationAccepted` events in `engine_events` |
| Primary key | `observation_id` |
| Ordering | `global_position` (monotonic ledger position) |
| Isolation | Every row carries `tenant_id`, `owner_id`, `application_id` from the source event |

The projection is updated inline on observation submission (same transaction as the event append) **and** can be fully rebuilt from the ledger at any time. Inline updates are an optimization; rebuild-from-zero reproduces identical rows.

Read endpoints (`GET /api/v1/observations`, `GET /api/v1/observations/{id}`) query this table, scoped to the authenticated application's owner.

---

## 3. Rebuild semantics

> **Stage 1.1 update — non-destructive verify + atomic promote.** `verify`, `rebuild`, and
> `promote` are now separated (§3.1). `rebuild(from_scratch=True)` no longer mutates live
> in place; it builds into a shadow table and promotes atomically. `verify()` never touches
> live. See §3.1 and `docs/runbooks/PROJECTION_REBUILD.md`.

`ProjectionRebuildService.rebuild()` (`application/use_cases/projections.py`):

1. **From scratch** (`from_scratch=True`, default): replay all events from position 0 into
   `accepted_observations_shadow`, validate, then **atomically promote** the shadow into
   `accepted_observations` (delete + refill in one transaction) and clear the shadow.
2. **Resume** (`from_scratch=False`): read the checkpoint's `last_global_position`, apply
   events after that position directly to live (idempotent, forward-only).

For each event:

- **Handled:** `ObservationAccepted` → upsert row (idempotent replay)
- **Skipped:** identity, credential, permission, projection, and integrity event types (no row effect)
- **Unknown:** any other event type → **STOP** rebuild, mark checkpoint `QUARANTINED`, raise `UnknownProjectionEventError`

After a successful rebuild:

- Checkpoint updated to `READY` with SHA-256 checksum of all projected rows
- `ProjectionRebuilt` event appended to `engine_events`
- Audit record with measured health snapshot

Protected by tests: `PROJECTION_REBUILDS_FROM_ZERO`, `PROJECTION_REBUILD_IS_DETERMINISTIC`, `PROJECTION_CHECKPOINT_RESUMES`, `UNKNOWN_EVENT_STOPS_OR_QUARANTINES_BY_POLICY`.

### 3.1 Verify / rebuild / promote (Stage 1.1)

| Operation | Effect on live |
|---|---|
| `verify()` | **None.** Replays into `accepted_observations_shadow`, checksums it, compares to live, cleans the shadow, and returns a `VerifyReport` (`matches`, `live_checksum`, `shadow_checksum`, `quarantined`). Live is never read-locked or modified. |
| `rebuild(from_scratch=True)` | Builds the shadow, validates, then promotes atomically. If validation succeeds live is replaced in one transaction; on unknown event the shadow reconstruction is quarantined and cleaned, live is left intact, and `UnknownProjectionEventError` is raised **before** any promotion. |
| `rebuild(from_scratch=False)` | Applies only post-checkpoint events directly to live (idempotent catch-up). |

`accepted_observations_shadow` has the same column shape as the live table. Promotion is a
single-transaction delete-and-refill, so it commits or rolls back as one unit
(`REBUILD_PROMOTION_IS_ATOMIC`, `FAILED_PROMOTION_ROLLS_BACK`). A verify that hits an unknown
event reports `quarantined=True` and leaves live untouched
(`UNKNOWN_EVENT_IN_SHADOW_DOES_NOT_EMPTY_LIVE`, `VERIFY_DOES_NOT_MUTATE_LIVE_PROJECTION`).
Tests: `tests/integration/test_shadow_projection.py`.

---

## 4. Checkpoints

Table: `projection_checkpoints`

| Column | Meaning |
|---|---|
| `projection_name` | e.g. `accepted_observations` |
| `projection_version` | e.g. `1.0` |
| `owner_scope` / `application_scope` | `ALL` (global rebuild scope in Stage 1) |
| `last_global_position` | Last successfully applied ledger position |
| `last_event_id` | Last event id at checkpoint |
| `status` | `READY` or `QUARANTINED` |
| `checksum` | SHA-256 of canonical row material (null when quarantined) |
| `updated_at` | Last checkpoint write |

**Chosen scoping model (Stage 1.1, explicit).** `accepted_observations` uses the **global
checkpoint model**: exactly one checkpoint row with `owner_scope = ALL` and
`application_scope = ALL`. Checkpoint lookups by `(projection_name, projection_version)` are
therefore unambiguous — there is no false appearance of per-application checkpoints. Rows in
the projection remain isolated by `tenant_id`/`owner_id`/`application_id`, and the read API
never exposes cross-application data, so a global rebuild checkpoint is safe and is declared
as the contract here.

### Append-only exception

`projection_checkpoints` is **mutable derived state**. Unlike `engine_events` and `audit_records`, checkpoint rows may be **UPDATE**d (rebuilds update the single row per scope). **DELETE** and **TRUNCATE** are blocked by PostgreSQL triggers and role grants. The Stage 1.1 control tables `event_stream_heads` and `integrity_checkpoints` follow the same exception.

This is a documented exception to the append-only principle: checkpoints are disposable bookkeeping, not historical truth.

---

## 5. Rebuild history

Rebuild operations themselves are recorded as append-only events:

- `ProjectionRebuilt` — emitted after every successful rebuild (events applied, rows written, checksum, position)
- `ProjectionCheckpointCreated` — reserved for incremental checkpoint recording (catalog entry exists; primary checkpoint persistence is via the mutable table)

Rebuild history in `engine_events` is permanent and auditable.

---

## 6. Freshness metadata

List responses include projection freshness in the envelope `meta.freshness`:

- `projection_name`, `projection_version`, `projection_position`

Clients can detect stale reads when the checkpoint lags behind the ledger head.

---

## 7. Operator scripts

Thin wrappers around the CLI rebuild command:

| Script | Purpose |
|---|---|
| `scripts/projections/rebuild_all.ps1` | Full rebuild of `accepted_observations` from position 0 |
| `scripts/projections/verify_projections.ps1` | Non-destructive shadow verify (Stage 1.1); reports match, checksums, row counts |

`rebuild_all.ps1` invokes `python -m intelligence_maxxxing.cli rebuild-projections`;
`verify_projections.ps1` invokes `python -m intelligence_maxxxing.cli verify-projections`
(the live projection is left untouched). See `docs/runbooks/PROJECTION_REBUILD.md`.

---

## 8. Rules (non-negotiable)

1. Projections are **never** the primary source of truth.
2. Deleting projection rows is safe; rebuilding restores them from events.
3. **Never delete events** to test a rebuild — that destroys history.
4. Unknown event types fail closed (quarantine), not silently skip.
5. Projection writes do not mutate the ledger.

---

## 9. Explicitly not in Stage 1

- Multiple projection types beyond `accepted_observations`
- Per-owner/per-application checkpoint scoping (global `ALL` scope only)
- Automatic background projector (rebuild is operator/CLI triggered)
- Event-sourced snapshots or CQRS read-side versioning beyond `1.0`
