# WELLBEING EXISTING SMOKE CONTAMINATION AUDIT V1

## Target observation

`obs_ab746ef9d6c64732990a6e7fc4aaea15`

## Classification

`KNOWN_TEST` (evidence: SCALE_CONTRACT smoke script + source URI prefix `lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1`).  
Effective selection after sprint: `EXCLUDED_INVALIDATED` via append-only exclusion registry + known-ID registry.

## Included by old policy

**Yes.** Pre-sprint extractors selected all `life.daily_check_in.completed.v1` rows with no purpose/environment filter. The scale-contract live smoke queried productive V1/V2 endpoints and reported normalized averages equal to the synthetic `0_100` inputs (happiness=5, stress=10).

## Live recomputation status

PostgreSQL was down during this sprint session (`ConnectionTimeout`). Quantitative with/without recomputation against the live ledger is therefore **offline-modeled** from documented smoke values and extractor semantics.

## Scores with observation (modeled day)

| Metric | Value |
|--------|-------|
| Happiness (canonical) | 5.0 (`5 / 0_100`) |
| Stress (canonical) | 10.0 (`10 / 0_100`) |
| Sample contribution | +1 day if first-write for that calendar day |

## Scores without observation (effective after exclusion)

| Metric | Value |
|--------|-------|
| Happiness | prior personal days only (smoke day removed from effective set) |
| Stress | prior personal days only |
| Sample | personal sample size without the smoke day |

Exact personal H/S/C deltas require live Engine recompute once Docker is up; structural contamination of the input set is proven.

## Affected V1 snapshots

Any `wellbeing_v1@1.2` snapshot generated after smoke ingest and before exclusion that included that calendar day under first-write wins. Historical snapshot rows remain immutable; new snapshots use corrected selection.

## Affected V2 snapshots

Same window logic for `wellbeing_v2@2.1.0` SHADOW snapshots.

## Contamination verdict

**CONTAMINATION_CONFIRMED**

Rationale:

1. Smoke was written to the personal production ledger (documented observation ID).  
2. Old input selection had no structural exclusion.  
3. Productive V1 features at smoke time matched synthetic magnitudes exactly.  
4. Marker text alone is not the proof — source URI + script provenance + retained ID are.

## Correction mechanism

Append-only exclusion registry entry:

| Field | Value |
|-------|-------|
| target_observation_id | `obs_ab746ef9d6c64732990a6e7fc4aaea15` |
| reason_code | `TEST_OBSERVATION_IN_PRODUCTION_LEDGER` |
| actor_system | `wellbeing_test_isolation_v1` |
| evidence_report | this document |

Original observation bytes: **preserved**.  
No DELETE / no silent metadata rewrite.

## New snapshot IDs

Generated on next productive `GET wellbeing/current` after deploy (new IDs + new fingerprints + `input_selection_policy_version=wellbeing_input_selection_v1`). Not overwritten in place.

## Historical preservation

**Yes** — prior snapshot rows untouched.
