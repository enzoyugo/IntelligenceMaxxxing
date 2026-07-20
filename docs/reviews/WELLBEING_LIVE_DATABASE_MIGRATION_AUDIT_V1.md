# Wellbeing Live Database Migration Audit V1

**Date:** 2026-07-20  
**Engine entry HEAD:** `6cbc5a4`  
**Database:** Docker `intelligence_maxxxing_postgres` → `postgresql://…@127.0.0.1:5432/intelligence_maxxxing`

## Backup

```text
E:\IntelligenceMaxxxing\backups\pg_pre_wellbeing_activation_20260720_195049.dump
```

Taken with `pg_dump -Fc` before upgrade. No destructive downgrade performed.

## Revisions

| Step | Revision | Result |
|---|---|---|
| Before | `0004_stage3` | confirmed via `alembic current` |
| After | `0007_wellbeing_v2` (head) | `alembic upgrade head` OK |

Chain applied: `0004 → 0005_stage3_1 → 0006_wellbeing_v1 → 0007_wellbeing_v2`.

## Schema verification

Tables present:

- `wellbeing_formula_versions`
- `wellbeing_baselines`
- `wellbeing_feature_snapshots`
- `wellbeing_score_snapshots`
- `wellbeing_feedback`

V2 columns on `wellbeing_score_snapshots` present:

- `formula_status`, `input_fingerprint`, `change_state`
- `happiness_confidence`, `stress_confidence` (+ related V2 columns from 0007)

## Policy compliance

- No DB recreate
- No V1 snapshot wipe
- No automatic historical recalculation of old rows
- No destructive downgrade

## Rollback

1. Stop Engine  
2. Restore dump: `pg_restore` into a new DB or replace after maintenance window  
3. `alembic stamp 0004_stage3` only if restoring that dump  

Prefer restore-from-backup over `alembic downgrade` for safety.
