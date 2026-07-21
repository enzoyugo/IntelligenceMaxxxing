# WELLBEING TEST OBSERVATION ISOLATION — Phase 0 Audit

## Baselines (session start)

| Repo | HEAD | Branch | Remote | Working tree |
|------|------|--------|--------|--------------|
| IntelligenceMaxxxing | `ecb9831` | `main` | `main == origin/main` | dirty once sprint edits began |
| LifeOS | `a3ebe14` | `main` | `main == origin/main` | dirty (unrelated prior UI files present; isolation touches scoped) |

## Known entry state

| Item | Value |
|------|-------|
| Prior scale contract | `WELLBEING_OBSERVATION_SCALE_CONTRACT_V1_PASS_WITH_WARNINGS` |
| V1 | `wellbeing_v1@1.2` ACTIVE |
| V2 | `wellbeing_v2@2.1.0` SHADOW |
| Measurement | `wellbeing_measurements_v1` |
| Normalization | `canonical_0_100_v1` |
| Contaminating smoke ID | `obs_ab746ef9d6c64732990a6e7fc4aaea15` |
| Marker (non-authoritative) | `E2E_SCALE_CONTRACT_V1` |
| Event | `life.daily_check_in.completed.v1` |

## Live DB status at Phase 0

Docker Desktop PostgreSQL was **unavailable** (`dockerDesktopLinuxEngine` pipe missing). Live SQL audit of global positions deferred; offline classification used documented smoke evidence + source URI prefix.

## Pipeline map (pre-change)

| Stage | Finding |
|-------|---------|
| Ingest | `SubmitObservationUseCase` → Event Store; no purpose/env gate |
| Projection | `accepted_observations` rebuildable |
| Extract V1 | `extract_checkin_days` — first-write wins by `global_position` |
| Extract V2 | `extract_day_records` — same ordering semantics |
| Selection | **None** — smoke/E2E not structurally excluded |
| Smoke script | LifeOS `wellbeing_scale_contract_e2e.ps1` wrote to personal BFF/Engine |

## Target observation (documented)

| Field | Value |
|-------|-------|
| Observation ID | `obs_ab746ef9d6c64732990a6e7fc4aaea15` |
| Global position | *live SQL unavailable this session* |
| Occurred at | smoke day UTC ~19:15 (script) |
| Event type | `life.daily_check_in.completed.v1` |
| Source IDs | `lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-*` |
| Purpose metadata | absent (pre-contract) |
| Subject/profile | personal production scope (default) |
| Environment | absent / implicit production ledger |
| Included in V1 (old policy)? | **Yes** — productive extract had no test filter; prior E2E reported `avg_happiness_normalized=5.0`, `avg_stress_normalized=10.0` matching smoke `0_100` values |
| Included in V2 (old policy)? | **Yes** (same extract path family) |
| Affected snapshot IDs | *live listing unavailable; any snapshot computed after ingest until exclusion* |
| Confidence impact | Possible inflation/deflation of sample size and confidence via synthetic day |
| Classification confidence | High for “entered productive extract path”; medium for exact same-day first-write vs personal without live positions |

## Technical observation discovery method

Evidence-backed only:

1. Known smoke script + retained observation ID from SCALE_CONTRACT master report  
2. Known source URI prefixes (`smoke-E2E_SCALE_CONTRACT_V1`, `smoke-E2E_WELLBEING_ACTIVATION`)  
3. Explicit exclusion registry bootstrap  
4. **Not** bare substring match on observation IDs alone  

## Gap summary

No typed `environment` / `observation_purpose` / `subject_scope` on productive path.  
No append-only invalidation.  
Smokes targeted personal ledger.  
First-write wins could let a test capture a calendar day.
