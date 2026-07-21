# WELLBEING APPEND-ONLY INVALIDATION V1

## Mechanism

In-process append-only exclusion registry:

`domain_packs/life/exclusion_registry.py`

Bootstrap entry for the SCALE_CONTRACT smoke observation. Runtime `append_exclusion()` is idempotent per target ID.

## Record fields

| Field | Example |
|-------|---------|
| target_observation_id | `obs_ab746ef9d6c64732990a6e7fc4aaea15` |
| reason_code | `TEST_OBSERVATION_IN_PRODUCTION_LEDGER` |
| reason | human-readable |
| invalidated_at | ISO-8601 UTC |
| actor_system | `wellbeing_test_isolation_v1` |
| evidence_report | audit doc name |

## Effective read model

`classify_for_personal_production(..., exclusion_ids=exclusion_id_set())` → `EXCLUDED_INVALIDATED`.

## Forbidden operations (not performed)

- `DELETE FROM observations` / ledger rows  
- Silent rewrite of original metadata / domain_pack / occurred_at  
- Reordering global positions  
- Overwriting historical wellbeing snapshots  

## Audit tooling

`scripts/audit/wellbeing_test_observation_audit.py`

- default: classify only  
- `--emit-invalidation-plan`: plan JSON, **no apply**
