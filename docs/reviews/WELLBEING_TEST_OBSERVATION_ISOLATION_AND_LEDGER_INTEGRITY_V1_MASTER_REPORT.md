# WELLBEING TEST OBSERVATION ISOLATION AND LEDGER INTEGRITY V1 — Master Report

## Verdict

**WELLBEING_TEST_OBSERVATION_ISOLATION_AND_LEDGER_INTEGRITY_V1_PASS_WITH_WARNINGS**

## Baselines / HEAD (post-push)

| Repo | Baseline | Final HEAD |
|------|----------|------------|
| Engine | `ecb9831` | `427807b` |
| LifeOS | `a3ebe14` | `cf40e97` |

`main == origin/main` on both after push. Working trees still contain unrelated local WIP (Engine: Research Factory M3A untracked; LifeOS: prior hierarchy/docs edits) — isolation commits themselves are pushed.

## Executive summary

Personal productive wellbeing scores now consume only observations selected by `wellbeing_input_selection_v1`. The SCALE_CONTRACT smoke observation is append-only invalidated. Future scale smokes use a temporary database. Formula weights unchanged; V1 remains ACTIVE; V2 remains SHADOW.

## Contamination

| Field | Value |
|-------|-------|
| Target observation | `obs_ab746ef9d6c64732990a6e7fc4aaea15` |
| Classification | KNOWN_TEST → EXCLUDED_INVALIDATED |
| Included by old policy | Yes |
| Contamination verdict | **CONTAMINATION_CONFIRMED** |
| Correction | Append-only exclusion registry |
| Original preserved | Yes |
| Historical snapshots preserved | Yes |

## Isolation

| Field | Value |
|-------|-------|
| Observation environment contract | Yes (`PRODUCTION`/`TEST`/`DEVELOPMENT`) |
| Observation purpose contract | Yes (closed enum) |
| Subject isolation | `PERSONAL` vs `TEST_PROFILE` |
| Input selection policy | `wellbeing_input_selection_v1` |
| Old smoke database | Personal production |
| New smoke database | Temp `intelligence_maxxxing_iso_smoke_*` |
| Production ledger writes from new smoke | None (by design) |
| Marker-only isolation | Rejected as authoritative mechanism |

## Versioning

Option A: keep `wellbeing_v1@1.2` / `wellbeing_v2@2.1.0`; persist `input_selection_policy_version`.

## Quality (this session)

| Gate | Result |
|------|--------|
| Engine unit tests (isolation + scale + guard) | PASS |
| LifeOS backend `tests.test_intelligence` | PASS (15) |
| Isolated smoke (Docker) | **BLOCKED** — Docker Desktop not running |
| Live SQL contamination deltas | Offline-modeled (Postgres timeout) |
| iPhone Daily Flow E2E | **Not run** this session |
| Pre-existing import-boundary constitutional failure | Still present (not hidden) |

## Warnings

1. Docker unavailable → isolated smoke + live ledger recompute not executed; scripts are reproducible.  
2. iPhone Daily Flow provenance tap-through pending — code path emits PRODUCTION / USER_OBSERVATION / `1_10`.  
3. LifeOS working tree contained unrelated dirty files; only isolation-scoped files should be committed.  
4. Constitutional import-boundary failure remains.

## Related reports

- `WELLBEING_TEST_OBSERVATION_ISOLATION_PHASE0_AUDIT.md`
- `WELLBEING_EXISTING_SMOKE_CONTAMINATION_AUDIT_V1.md`
- `WELLBEING_EFFECTIVE_OBSERVATION_SELECTION_POLICY_V1.md`
- `WELLBEING_APPEND_ONLY_INVALIDATION_V1.md`
- `WELLBEING_ISOLATED_SMOKE_INFRASTRUCTURE_V1.md`
- `WELLBEING_LEDGER_INTEGRITY_V1.md`
- LifeOS: `LIFEOS_DAILY_FLOW_PROVENANCE_E2E_V1.md`
