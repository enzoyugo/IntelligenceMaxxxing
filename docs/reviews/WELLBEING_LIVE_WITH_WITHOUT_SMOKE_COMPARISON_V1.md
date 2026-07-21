# WELLBEING LIVE WITH/WITHOUT SMOKE COMPARISON V1

## Target

`obs_ab746ef9d6c64732990a6e7fc4aaea15` @ global_position **16**  
Source: `lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-2026-07-21`  
Occurred: `2026-07-21T19:15:00+00:00`

## Correction (live DB)

| Field | Value |
|-------|-------|
| Original observation | PRESENT |
| Correction record | PRESENT (`excl_scale_contract_smoke_v1`) |
| Effective | EXCLUDED_INVALIDATED |
| Reason | `TEST_OBSERVATION_IN_PRODUCTION_LEDGER` |
| Migration | `0008_observation_exclusion` |

## Metric table (V1, window 14)

| Metric | With smoke (old effective) | Without smoke (`wellbeing_input_selection_v1`) | Delta |
|--------|----------------------------|-----------------------------------------------|-------|
| Happiness | 9.4 | null | −9.4 |
| Stress | 10.0 | null | −10.0 |
| Confidence | 45.0 | 31.23 | −13.77 |
| Sample size | 6 | 5 | −1 |

Interpretation: the synthetic smoke day was the only window day supplying normalized happiness/stress averages under the contaminated set; excluding it removes that day (sample 6→5) and clears those averages until a personal Daily Flow with scores lands.

## New effective snapshots (historical preserved)

| | Old (examples remain in table) | New |
|--|-------------------------------|-----|
| V1 | prior rows untouched | `wbs_bb59f9a93c5e4f34bdea2d23e618f0dd` @1.2 ACTIVE |
| V2 | prior rows untouched | `wbs_cce102a415584418b23766954f72871b` @2.1.0 SHADOW |

New snapshot features:

- `input_selection_policy_version` = `wellbeing_input_selection_v1`
- `excluded_test_count` = 1
- `excluded_invalidated_count` = 1
- `included_observation_count` = 5

## Versioning

Kept **Option A**: `wellbeing_v1@1.2` ACTIVE, `wellbeing_v2@2.1.0` SHADOW.
