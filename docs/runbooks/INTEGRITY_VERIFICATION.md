# Integrity Verification — Stage 1

**Audience:** Operators auditing ledger tamper detection  
**Code:** `application/use_cases/integrity.py`, `domain/audit/integrity.py`

---

## 1. Purpose

Stage 1 maintains a deterministic hash chain over `engine_events`, scoped per **`(owner_id, application_id)` stream**. Each event's `event_hash` chains to the previous event's hash within the same stream.

This is **tamper/corruption detection**, not absolute cryptographic security. An attacker with full database write access and knowledge of the scheme could rewrite an entire stream. The goal is to make **silent alteration detectable**.

---

## 2. Chain scope

```text
Stream key: (owner_id, application_id)
Ordering:   global_position ascending within stream
Genesis:    first event may have event_hash = NULL (legacy Stage 0 rows)
Chain start: first event with a non-null event_hash
```

Unrelated applications never share a chain head. Legacy events without hashes are tolerated only before the chain begins.

Hash material includes canonical event fields plus `previous_event_hash`, `actor_type`, and `actor_id` (`domain/audit/integrity.py`).

---

## 3. Verification modes

| Mode | Behavior |
|---|---|
| `FULL` | Verify all events in every stream from position 0 (default) |
| `INCREMENTAL` | Verify events from `since_position` onward (CLI accepts `--mode INCREMENTAL`) |

Both modes append an `IntegrityCheckCompleted` event and audit record on every run.

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

When a broken link is detected:

1. **`IntegrityViolationDetected`** event appended (one per violation)
2. **Kill-switch hook** invoked: `IntegrityViolationHookPort.on_violation()`
3. Default implementation (`LoggingIntegrityViolationHook`) writes a structured error log

Stage 1 does **not** automatically pause writes for the broken stream. Future stages may escalate the hook to block submissions for the affected `(owner_id, application_id)`.

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

Both are catalog-registered and stored in `engine_events`.

---

## 9. Explicitly not in Stage 1

- Automatic scheduled verification
- HTTP endpoint for integrity checks
- HSM or external signing
- Cross-replica chain consensus
- Write-path blocking on violation (hook logs only)

See also: `docs/architecture/EVENT_CATALOG.md`, `docs/architecture/POSTGRES_APPEND_ONLY_ENFORCEMENT.md`.
