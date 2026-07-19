# Stream Head and Quarantine Model — Stage 1.1

**Status:** IMPLEMENTED (Stage 1.1)
**Authority:** Constitution Art. 34 (append-only history), Technical Architecture §8
**Code:** `infrastructure/event_store/sqlalchemy_event_store.py`, `infrastructure/repositories/integrity.py`, `application/use_cases/integrity.py`, `application/ports/stores.py`, `migrations/versions/0003_stage1_1_integrity_isolation_hardening.py`

---

## 1. Why this exists

Stage 1 chained events per stream with a *read-then-write* flow:

```text
read latest hash  →  compute hash  →  insert event
```

Between the read and the insert, a second concurrent writer of the same stream could
read the **same** latest hash. Two distinct events would then both point at the same
`previous_event_hash`, forking the chain. Under real multi-session PostgreSQL this is a
live defect, not a theoretical one.

Stage 1.1 replaces the read-then-write with a **transactional stream head** that
serializes writers of the same stream, and adds a **real quarantine kill-switch** that
blocks writes to a stream once a break is detected.

---

## 2. Stream identity

A stream is one integrity chain. Its identity is the full isolation triple:

```text
(tenant_id, owner_id, application_id)
```

This matches audit and aggregate isolation (see `IDENTITY_AND_PERMISSION_MODEL.md`):
two applications under the same owner are **different** streams and never share a head.

---

## 3. `event_stream_heads`

The single mutable row that represents the current tip of a stream.

| Column | Meaning |
|---|---|
| `tenant_id`, `owner_id`, `application_id` | Primary key (the stream key) |
| `last_global_position` | Ledger position of the last chained event |
| `last_event_id` | Event id of the last chained event |
| `current_event_hash` | Hash of the last chained event — the **anchor** for the next append |
| `stream_version` | Monotonic count of appends to this stream |
| `status` | `ACTIVE` · `QUARANTINED` · `REBUILD_REQUIRED` |
| `quarantine_reason`, `broken_event_id`, `quarantined_at`, `quarantine_audit_id` | Populated on quarantine |
| `updated_at` | Last head write |

The head is engine-managed **control state**, not ledger evidence. It may be UPDATEd
through the governed append/quarantine/release paths, but never lets the runtime rewrite
events or audits.

---

## 4. Append flow (single event)

Inside one transaction (`SqlAlchemyEventStore.append_one`):

1. **Ensure the head exists, race-safe.** On PostgreSQL:
   `INSERT ... ON CONFLICT (tenant_id, owner_id, application_id) DO NOTHING`. On SQLite
   the writer is serialized by the database, so a get-or-create is sufficient.
2. **Lock the head:** `SELECT ... FOR UPDATE`. Concurrent writers of the same stream now
   serialize here instead of forking. On SQLite the clause is a harmless no-op because
   SQLite already serializes writers.
3. **Reject if not `ACTIVE`:** a `QUARANTINED` stream raises `StreamQuarantinedError`
   *before* any insert.
4. **Chain:** `previous_event_hash = head.current_event_hash`, compute `event_hash`.
5. **Insert** the event.
6. **Advance the head:** `current_event_hash`, `last_event_id`, `last_global_position`,
   `stream_version += 1`.
7. **Commit atomically.** If the commit fails (e.g. the scoped aggregate unique
   constraint), the head advance rolls back with it — a failed append never advances the
   head.

The guarantee holds **across processes**, not just across Python threads: it is enforced
by the row lock in PostgreSQL, not by an in-process lock.

### `pg_advisory_xact_lock` — not used

An advisory-lock variant was considered. We chose the `event_stream_heads` row lock
because the head row is also the durable anchor we must read and update anyway; a single
`SELECT ... FOR UPDATE` gives both mutual exclusion and the previous hash without a second
derived lock key that could silently collide.

---

## 5. `append_batch`

For atomic multi-event appends:

1. Group events by stream key, preserving per-stream input order.
2. Lock stream heads in a **deterministic order** (sorted by key) to avoid deadlocks
   between concurrent batches.
3. Chain each stream's events in input order onto its head.
4. Return events in the original input order.

`APPEND_BATCH_CHAINS_IN_INPUT_ORDER` verifies the per-stream chain follows input order.

---

## 6. Quarantine (the real kill-switch)

Detection lives in `IntegrityVerificationService.verify()`. When a stream's chain is
broken:

1. `IntegrityViolationHookPort.on_violation(...)` fires (structured error log).
2. `IntegrityStorePort.quarantine_stream(...)` sets `status = QUARANTINED` and records
   `reason`, `broken_event_id`, `detected_at`, `quarantine_audit_id`.
3. Two append-only events are written to the SYSTEM stream:
   `IntegrityViolationDetected` and `IntegrityStreamQuarantined`.

From that moment every `append_one`/`append_batch` to the quarantined stream is rejected
with `StreamQuarantinedError` → **HTTP 409** (see below). Other streams are unaffected.

### Why 409, not 503

A quarantine is a **durable state conflict** that requires a governed release, not a
transient outage that a client should retry. `409 Conflict` is returned consistently
across the API (`api/errors.py`). `503` would wrongly invite automatic retries.

---

## 7. Release (governed, CLI-only)

A quarantined stream is only released through the local admin CLI:

```powershell
python -m intelligence_maxxxing.cli inspect-stream       --tenant-id ... --owner-id ... --application-id ...
python -m intelligence_maxxxing.cli verify-stream         --tenant-id ... --owner-id ... --application-id ...
python -m intelligence_maxxxing.cli unquarantine-stream   --tenant-id ... --owner-id ... --application-id ... --reason "..."
```

`unquarantine_stream` enforces, in order:

1. **`ADMINISTER_ENGINE` scope** — otherwise `StreamReleaseBlockedError`.
2. **A successful FULL verification** of the stream — a still-broken stream cannot be
   released, even by an admin.
3. On success: `release_stream(...)` sets `status = ACTIVE` and an `IntegrityStreamReleased`
   append-only event is written with `reason` and `released_by`.

There is no HTTP path and no implicit release. The runtime role can update head/checkpoint
control state through these governed methods but can never clear a quarantine arbitrarily.

---

## 8. Integrity checkpoints (incremental anchor)

`integrity_checkpoints` stores the last reliably verified point per stream:

| Column | Meaning |
|---|---|
| `tenant_id`, `owner_id`, `application_id` | Primary key |
| `last_verified_global_position` | Position of the last verified event |
| `last_verified_event_id` | Event id of the last verified event |
| `last_verified_hash` | **Anchor** for the first event after the checkpoint |
| `verified_at`, `status` | Bookkeeping |

INCREMENTAL verification resumes after the checkpoint and passes `last_verified_hash` as
`initial_previous_hash` to `verify_chain(...)`, so a legitimate mid-stream start is never
mistaken for corruption. The checkpoint is advanced **only** when the newer range verifies
cleanly — never on failure. See `docs/runbooks/INTEGRITY_VERIFICATION.md`.

---

## 9. Append-only posture of control tables

| Table | UPDATE | DELETE | TRUNCATE |
|---|---|---|---|
| `event_stream_heads` | allowed (governed) | blocked | blocked |
| `integrity_checkpoints` | allowed (governed) | blocked | blocked |

Like `projection_checkpoints`, these are mutable derived control state, not historical
truth: rows advance forward but cannot be deleted or truncated by the runtime. The ledger
(`engine_events`, `audit_records`) remains strictly append-only.

---

## 10. Tests

Real multi-session PostgreSQL (`tests/postgres/test_stage1_1_hardening.py`):

- `CONCURRENT_DISTINCT_EVENTS_SAME_STREAM_FORM_ONE_CHAIN` — 20 concurrent appends → 20
  events, one valid chain, one head, head hash == last event hash
- `CONCURRENT_EVENTS_DIFFERENT_STREAMS_DO_NOT_BLOCK_GLOBALLY`
- `STREAM_HEAD_MATCHES_LAST_EVENT`, `APPEND_BATCH_CHAINS_IN_INPUT_ORDER`
- `STREAM_HEAD_UPDATE_IS_ATOMIC`, `FAILED_APPEND_DOES_NOT_ADVANCE_STREAM_HEAD`
- `QUARANTINED_STREAM_REJECTS_APPEND`

Quarantine behavior (`tests/integration/test_quarantine.py`) and incremental integrity
(`tests/unit/test_integrity_incremental.py`) run on hermetic SQLite; concurrency and chain
guarantees are proven on **real PostgreSQL only** — SQLite is never presented as equivalent
for the cross-process guarantee.
