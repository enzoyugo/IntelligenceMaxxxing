# Integrity Verification — Stage 1

**Audience:** Operators auditing ledger tamper detection  
**Code:** `application/use_cases/integrity.py`, `domain/audit/integrity.py`

---

## 1. Purpose

> **Stage 1.1 update.** Streams are now keyed by the full triple **`(tenant_id, owner_id,
> application_id)`**; a detected break **quarantines** the stream and blocks new writes
> (§5); INCREMENTAL verification uses a checkpoint hash as an anchor (§3.1). This section
> documents the Stage 1.1 behavior.

Stage 1 maintains a deterministic hash chain over `engine_events`, scoped per stream. Each event's `event_hash` chains to the previous event's hash within the same stream.

This is **tamper/corruption detection**, not absolute cryptographic security. An attacker with full database write access and knowledge of the scheme could rewrite an entire stream. The goal is to make **silent alteration detectable**.

---

## 2. Chain scope

```text
Stream key: (tenant_id, owner_id, application_id)   # Stage 1.1
Ordering:   global_position ascending within stream
Genesis:    first event may have event_hash = NULL (legacy Stage 0 rows)
Chain start: first event with a non-null event_hash
Head:        event_stream_heads holds the current tip + status (Stage 1.1)
```

Unrelated applications never share a chain head. Legacy events without hashes are tolerated only before the chain begins.

Hash material includes canonical event fields plus `previous_event_hash`, `actor_type`, and `actor_id` (`domain/audit/integrity.py`).

---

## 3. Verification modes

| Mode | Behavior |
|---|---|
| `FULL` | Verify all events in every stream from position 0 (default); advance the integrity checkpoint on success |
| `INCREMENTAL` | Resume after each stream's `integrity_checkpoints` row, using `last_verified_hash` as the anchor; verify only newer events |

Both modes append an `IntegrityCheckCompleted` event and audit record on every run.

### 3.1 Incremental anchor and checkpoints (Stage 1.1)

`integrity_checkpoints` (PK `(tenant_id, owner_id, application_id)`) records the last
reliably verified `global_position`, `event_id`, and `hash` per stream. INCREMENTAL
verification passes that hash into `verify_chain(events, initial_previous_hash=...)`, so the
first event after the checkpoint chains onto a **trusted anchor** and a legitimate mid-stream
start is never mistaken for corruption. The checkpoint is advanced **only when the newer
range verifies cleanly** — never on failure. With no checkpoint, INCREMENTAL falls back to a
FULL verification from position 0. Tests: `tests/unit/test_integrity_incremental.py`.

---

## 4. CLI verification

```powershell
python -m intelligence_maxxxing.cli verify-integrity
python -m intelligence_maxxxing.cli verify-integrity --mode INCREMENTAL
```

Output:

```text
ok=True streams=3 events=42 violations=0
```

Exit code `0` = all streams valid; exit code `2` = at least one violation.

Violations print:

```text
violation owner=usr_... app=app_... event=evt_...
```

---

## 5. Violation handling

When a broken link is detected (Stage 1.1 — real kill-switch):

1. **Kill-switch hook** invoked: `IntegrityViolationHookPort.on_violation()` (structured log)
2. The stream head is set to **`QUARANTINED`** with `reason`, `broken_event_id`,
   `detected_at`, and `quarantine_audit_id`
3. **`IntegrityViolationDetected`** and **`IntegrityStreamQuarantined`** events appended
4. Every subsequent append to that stream is rejected with `StreamQuarantinedError` →
   **HTTP 409**; other streams stay available

### 5.1 Releasing a quarantined stream (CLI-only)

```powershell
python -m intelligence_maxxxing.cli inspect-stream     --tenant-id ... --owner-id ... --application-id ...
python -m intelligence_maxxxing.cli verify-stream       --tenant-id ... --owner-id ... --application-id ...
python -m intelligence_maxxxing.cli unquarantine-stream --tenant-id ... --owner-id ... --application-id ... --reason "..."
```

Release requires **`ADMINISTER_ENGINE`** scope **and** a successful FULL verification of the
stream; it emits an `IntegrityStreamReleased` append-only event. There is no HTTP path and no
implicit release. See `docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md`. Tests:
`tests/integration/test_quarantine.py`, `tests/postgres/test_stage1_1_hardening.py`.

---

## 6. When to run

- After extraordinary maintenance (see `POSTGRES_APPEND_ONLY_ENFORCEMENT.md`)
- After restoring from backup
- Periodic operator audit (recommended before major upgrades)
- After any suspicion of direct database tampering

---

## 7. Interpreting results

| Result | Meaning |
|---|---|
| `ok=True`, 0 violations | All checked streams intact |
| `ok=False`, violations listed | Hash mismatch or broken previous link at listed event |
| Legacy rows at stream start | Normal for Stage 0 data migrated into Stage 1 |

Do not treat a passing check as proof against a sophisticated insider with superuser access.

---

## 8. Related events

| Event | When |
|---|---|
| `IntegrityCheckCompleted` | Every verification run |
| `IntegrityViolationDetected` | Each broken stream detected |
| `IntegrityStreamQuarantined` | Stream set to QUARANTINED after a break (Stage 1.1) |
| `IntegrityStreamVerified` | Full verification of a single stream via `verify-stream` (Stage 1.1) |
| `IntegrityStreamReleased` | Governed release via `unquarantine-stream` (Stage 1.1) |

All are catalog-registered and stored in `engine_events`.

---

## 9. Explicitly not in Stage 1

- Automatic scheduled verification (verification is still operator/CLI-triggered)
- HTTP endpoint for integrity checks
- HSM or external signing
- Cross-replica chain consensus

Write-path blocking on violation is **now implemented** in Stage 1.1 (quarantine kill-switch, §5); it is no longer a Stage 1 limitation.

See also: `docs/architecture/EVENT_CATALOG.md`, `docs/architecture/POSTGRES_APPEND_ONLY_ENFORCEMENT.md`.
