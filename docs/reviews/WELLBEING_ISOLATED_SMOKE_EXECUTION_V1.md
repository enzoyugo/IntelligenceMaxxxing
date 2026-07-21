# WELLBEING ISOLATED SMOKE EXECUTION V1

## Result

**PASS** — temporary database, Engine :8117, cleanup destroyed DB.

| Field | Value |
|-------|-------|
| Temporary database | `intelligence_maxxxing_iso_smoke_20260721192454` |
| Temporary Engine port | `8117` |
| Test subject / run | `test-f51e4244931b4567903fc2c89143c5fd` |
| Environment | `TEST` |
| Purpose | `SMOKE_TEST` |
| Observation ID | `obs_65b2e6d1b0894d8992994e0bc870240b` |
| V1 sample_size | 1 |
| Excluded test count | 1 |
| Input policy | `wellbeing_input_selection_v1` |
| Cleanup | Temporary database destroyed |

## Personal ledger invariant

| Metric | Before | After |
|--------|--------|-------|
| accepted_observation_count | 7 | 7 |
| latest_global_position | 16 | 16 |

**No change caused by isolated smoke.**

## Guardrails exercised

- Refuses non-isolated mode
- Temp DB name contains `iso_smoke`
- Port 8117 (not 8100)
- Canary refuses URL containing 8100
