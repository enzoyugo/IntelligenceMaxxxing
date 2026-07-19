# OFFLINE SYNC CONTRACT

**Status:** Technical contract (Stage 0: CONTRACT_ONLY)
**Parent authority:** Constitution v1.1 (Art. 43-A), Engine Service Contract v1.0 (§9, §11)
**Implementation status:** The server-side idempotency guarantees are implemented in Stage 0.
The client-side offline queue is NOT implemented and belongs to each application (first: LifeMaxxxing, Stage 3).

---

## 1. Purpose

Applications must be able to operate partially offline, queue observations and
outcomes locally, and synchronize later **without duplicating anything** and
**without inventing intelligence** while disconnected.

This document freezes the technical contract both sides must honor. Nothing
here simulates a working queue; it defines what the queue must look like.

---

## 2. Client queue entry (required fields)

Every locally queued write must preserve:

| Field | Type | Meaning |
|---|---|---|
| `client_event_id` | string, unique per client | Local identity of the queued entry; never reused |
| `idempotency_key` | string ≤ 256 chars | Sent as `Idempotency-Key`; stable across retries of the same logical event |
| `created_at` | ISO-8601 UTC | When the entry was created locally (offline time) |
| `schema_version` | string `MAJOR.MINOR` | Contract version the payload was built against |
| `sync_state` | enum | `PENDING`, `IN_FLIGHT`, `SYNCED`, `CONFLICT`, `REJECTED` |
| `retry_count` | integer | Incremented on each attempt |
| `payload` | JSON | The exact request body, immutable once queued |

Recommended key construction: `"{app_id}:{client_event_id}"`. The key must be
generated **once**, when the entry is queued — never per attempt.

## 3. Sync state machine

```text
PENDING -> IN_FLIGHT -> SYNCED
                     -> CONFLICT   (409: same key, different payload)
                     -> REJECTED   (422: schema/validation failure)
IN_FLIGHT -> PENDING               (network failure: retry later, same key)
```

- `SYNCED` entries store the returned `observation_id`, `event_id`, `audit_id`.
- `CONFLICT` and `REJECTED` entries are never silently dropped or mutated;
  they require explicit handling (new logical event = new key).

## 4. Engine-side guarantees (implemented in Stage 0)

1. **Safe retry:** the same `Idempotency-Key` with a byte-equivalent payload
   returns the original result (`replayed: true`, HTTP 200). No new
   observation, event, or audit record is created.
2. **Conflict detection:** the same key with a different payload returns
   HTTP 409 with error code `IDEMPOTENCY_CONFLICT` and creates nothing.
3. **No duplication:** uniqueness is enforced in the database
   (`uq_idempotency_scope_key`, `uq_engine_events_idempotency_scope_key`),
   not only in application code.
4. **Auditability:** every accepted write returns an `audit_id` recoverable
   through `GET /api/v1/audits/{audit_id}`.

## 5. Offline behavior rules (for future application adapters)

While the Engine is unreachable, applications must:

- keep local features working;
- show the last valid Engine result marked `STALE`;
- never fabricate new intelligence locally;
- queue writes with the fields in §2;
- block critical execution paths;
- replay the queue in `created_at` order on reconnection, one logical event
  at a time, honoring the state machine in §3.

## 6. Deferred (not in Stage 0)

- The LifeMaxxxing local queue implementation (Stage 3).
- Batch sync endpoint.
- Server-side per-application sync cursors.
- Push notifications of Engine events back to applications.
