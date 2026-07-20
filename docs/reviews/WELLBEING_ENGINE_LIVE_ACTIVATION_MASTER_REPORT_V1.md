# Wellbeing Engine Live Activation — Master Report V1

**Companion to LifeOS sprint** `LIFEOS_WELLBEING_ENGINE_LIVE_ACTIVATION_AND_E2E_TRUTH_V1`

**Engine baseline:** `6cbc5a4`  
**Date:** 2026-07-20

## Delivered

- Live migrations to `0007_wellbeing_v2` (backup first)
- Public `/health/live` build identity (commit, api_version, wellbeing ACTIVE/SHADOW)
- Typed `UNKNOWN_FORMULA` for unknown `formula_id`
- SDK package version **0.3.0** (wellbeing client methods)
- Constitutional allowlist update for `POST /api/v1/wellbeing/feedback`
- Live V1 ACTIVE + V2 SHADOW snapshot E2E evidence

## Known constitutional warning

`test_application_layer_has_no_infrastructure_import` fails due to existing imports in:

- `application/use_cases/wellbeing.py` (SQLAlchemy/tables)
- `evaluate_experiment_v31.py`, `epistemic.py` (clock / sqlalchemy)

Not introduced by connectivity fix; full hexagonal cleanup is out of scope for this activation sprint.

## Reports

- `WELLBEING_LIVE_DATABASE_MIGRATION_AUDIT_V1.md`
- `WELLBEING_V1_V2_LIVE_SNAPSHOT_E2E_V1.md`
