# Projection Rebuild — Stage 1

**Audience:** Operators maintaining derived read models  
**Authority:** `docs/architecture/PROJECTION_MODEL.md`

---

## 1. When to rebuild

Rebuild `accepted_observations` when:

- Verifying ledger → projection consistency after maintenance
- Recovering from a quarantined checkpoint (`status = QUARANTINED`)
- Confirming deterministic replay after code changes
- Initial setup validation

Rebuilds are safe: projection rows are disposable. The ledger is not.

---

## 2. Never delete events

**Do not delete rows from `engine_events` to test a rebuild.** That destroys history and breaks the integrity chain. To test rebuild semantics:

1. Submit observations through the API (creates real events)
2. Run a rebuild
3. Compare row counts and checksums

Deleting projection rows alone is fine; deleting ledger events is not.

---

## 3. CLI rebuild

Full rebuild from position 0 (default):

```powershell
python -m intelligence_maxxxing.cli rebuild-projections
```

Resume from checkpoint:

```powershell
python -m intelligence_maxxxing.cli rebuild-projections --resume
```

Output includes: `projection`, `version`, `events_scanned`, `rows_written`, `position`, `checksum`.

On success, a `ProjectionRebuilt` event is appended to the ledger.

---

## 4. Operator scripts

| Script | Equivalent CLI |
|---|---|
| `scripts/projections/rebuild_all.ps1` | `rebuild-projections` (from scratch) |
| `scripts/projections/verify_projections.ps1` | `rebuild-projections` + checksum report |

Example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\projections\rebuild_all.ps1
powershell -ExecutionPolicy Bypass -File scripts\projections\verify_projections.ps1
```

Scripts invoke the CLI; they contain no projection logic of their own.

---

## 5. Quarantine behavior

If the projector encounters an unknown event type:

1. Rebuild **stops** immediately
2. Checkpoint set to `QUARANTINED` (checksum cleared)
3. `UnknownProjectionEventError` raised
4. Operator must register the event in the catalog and update handled/skipped lists before retrying

Known non-projection events (identity, permissions, integrity) are skipped safely.

---

## 6. Verification checklist

After rebuild:

- [ ] CLI exits 0
- [ ] Checkpoint status is `READY`
- [ ] `rows_written` matches expected `ObservationAccepted` count
- [ ] `GET /api/v1/observations` returns expected data (with valid credential)
- [ ] `ProjectionRebuilt` event exists in `engine_events`

---

## 7. Inline projection updates

Observation submission updates `accepted_observations` in the same transaction as the event append. A rebuild should reproduce the same rows. If inline and rebuild results diverge, treat as a bug — do not patch projection rows manually without investigating.

---

## 8. Explicitly not supported

- Rebuilding a subset of owner/application scopes (Stage 1 rebuilds globally)
- Background automatic rebuild scheduling
- Rebuild via HTTP endpoint
