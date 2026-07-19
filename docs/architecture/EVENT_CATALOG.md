# Event Catalog — Stage 1

**Status:** IMPLEMENTED (Stage 1)  
**Authority:** Technical Architecture §8–§9, Engine Service Contract §7  
**Code:** `src/intelligence_maxxxing/contracts/events/catalog.py`

---

## 1. Purpose

Every event type the Engine may append **must** be registered in the versioned event catalog. The event store validates every payload against the catalog before persisting. Unregistered event types or schema mismatches are rejected at append time.

Arbitrary event types cannot enter the ledger.

---

## 2. Catalog location and structure

The canonical registry is `contracts/events/catalog.py`:

- `EventTypeSpec` — declaration of one `(event_type, schema_version)` pair
- `EVENT_CATALOG` — frozen dict keyed by `(event_type, schema_version)`
- `get_event_spec()` — resolve a spec or raise `UnregisteredEventTypeError`
- `validate_event_payload()` — validate a payload dict against the registered schema

Each spec carries governance metadata: `aggregate_type`, `payload_model`, `owner`, `sensitivity`, `retention`, `producing_use_case`, `permitted_consumers`.

---

## 3. Validation pipeline

```text
event_type + schema_version
        │
        ▼
EVENT_CATALOG lookup → EventTypeSpec
        │
        ▼
payload_model.model_validate(payload)
        │
        ▼
append to engine_events (or reject)
```

Errors:

- Unknown pair → `UnregisteredEventTypeError`
- Payload fails schema → `EventPayloadInvalidError`

Protected by tests: `UNREGISTERED_EVENT_TYPE_REJECTED`, `WRONG_EVENT_SCHEMA_REJECTED` (`tests/unit/test_event_catalog.py`).

---

## 4. Registered event types (schema version 1.0)

All entries below use `schema_version = "1.0"` unless noted.

### Identity events

Payload schemas: `contracts/events/identity_events.py`

| Event type | Aggregate | Producing use case | Sensitivity |
|---|---|---|---|
| `ApplicationRegistered` | Application | `identity.register_application` | MEDIUM |
| `ApplicationCredentialCreated` | ApplicationCredential | `identity.create_credential` | HIGH |
| `ApplicationCredentialRotated` | ApplicationCredential | `identity.rotate_credential` | HIGH |
| `ApplicationCredentialRevoked` | ApplicationCredential | `identity.revoke_credential` | HIGH |
| `UserRegistered` | User | `identity.bootstrap_owner` | MEDIUM |
| `PermissionGranted` | Application | `identity.grant_scope` | HIGH |
| `PermissionRevoked` | Application | `identity.revoke_scope` | HIGH |

Credential events never contain the secret or its hash.

### Observation events

| Event type | Aggregate | Producing use case | Notes |
|---|---|---|---|
| `ObservationAccepted` | Observation | `observations.submit` | Payload = canonical `Observation` model |

**Backward compatibility:** `ObservationAccepted` 1.0 keeps the Stage 0 payload shape (the `Observation` contract). Existing Stage 0 events remain valid; no payload migration is required. Test: `OBSERVATION_ACCEPTED_V1_BACKWARD_COMPATIBLE`.

### Projection governance events

Payload schemas: `contracts/events/governance_events.py`

| Event type | Aggregate | Producing use case |
|---|---|---|
| `ProjectionRebuilt` | Projection | `projections.rebuild` |
| `ProjectionCheckpointCreated` | Projection | `projections.checkpoint` |

### Integrity governance events

| Event type | Aggregate | Producing use case |
|---|---|---|
| `IntegrityCheckCompleted` | IntegrityCheck | `integrity.verify` |
| `IntegrityViolationDetected` | IntegrityCheck | `integrity.verify` |

---

## 5. Storage

All catalog events — including identity, permission, projection, and integrity events — are stored in **`engine_events`**. There is no separate `governance_events` table.

Governance events use system actor identities (`SYSTEM_TENANT_ID`, `SYSTEM_OWNER_ID`, `SYSTEM_APPLICATION_ID`) when produced by CLI-driven use cases.

---

## 6. Retention and sensitivity

All registered events have `retention = PERMANENT` (ledger history is never deleted). Sensitivity levels (`LOW`, `MEDIUM`, `HIGH`) are declared for future access-control and export policies; Stage 1 does not enforce sensitivity-based filtering.

---

## 7. Adding a new event type

1. Define a frozen payload model under `contracts/events/`.
2. Register an `EventTypeSpec` in `catalog.py`.
3. Add catalog validation tests.
4. Update the projector's handled/skipped event lists if the event affects derived state.
5. Document the change; constitutional events require governance review.

Breaking changes to an existing `(event_type, schema_version)` pair are forbidden within a major API version. New schema versions require a new catalog entry.

---

## 8. Explicitly not in Stage 1

- Event type registration via HTTP
- Dynamic/runtime catalog extension
- Cross-engine event federation
- Event encryption or signing (integrity chain is separate; see `INTEGRITY_VERIFICATION.md`)
