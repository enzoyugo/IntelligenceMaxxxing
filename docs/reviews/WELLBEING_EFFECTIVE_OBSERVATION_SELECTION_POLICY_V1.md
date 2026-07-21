# WELLBEING EFFECTIVE OBSERVATION SELECTION POLICY V1

## Policy version

`wellbeing_input_selection_v1`

## Module

`domain_packs/life/input_selection.py`  
Provenance enums: `domain_packs/life/observation_provenance.py`

## Shared by

V1 (`extract_checkin_days`) and V2 (`extract_day_records`) — **same** `select_effective_observations` before first-write wins.

## Environments (closed)

`PRODUCTION` | `TEST` | `DEVELOPMENT`

## Purposes (closed)

`USER_OBSERVATION` | `SMOKE_TEST` | `CONTRACT_TEST` | `FIXTURE` | `MIGRATION` | `BACKFILL` | `DEMO`

## Subject scopes (closed)

`PERSONAL` | `TEST_PROFILE` | `SHARED_DEMO`

## Production inclusion rule (personal scores)

Effective equivalent of:

- not in exclusion registry  
- not known-test ID / known-test source prefix  
- purpose not in non-productive set  
- subject_scope ≠ `TEST_PROFILE`  
- environment ≠ `TEST`  
- for check-ins: `USER_OBSERVATION` under PRODUCTION/DEVELOPMENT (or legacy LifeOS personal URI without smoke prefix)  
- unsupported / ambiguous → excluded (never first-write by accident)

## Decisions

`INCLUDED` | `EXCLUDED_TEST` | `EXCLUDED_INVALIDATED` | `EXCLUDED_WRONG_SUBJECT` | `EXCLUDED_WRONG_ENVIRONMENT` | `EXCLUDED_UNSUPPORTED_CONTRACT` | `EXCLUDED_AMBIGUOUS`

## Snapshot features persisted

- `input_selection_policy_version`
- `included_observation_count`
- `excluded_test_count`
- `excluded_invalidated_count`
- `excluded_ambiguous_count`
- `subject_scope`
- `environment`

## Formula versioning decision — Option A

Keep:

- `wellbeing_v1@1.2` ACTIVE  
- `wellbeing_v2@2.1.0` SHADOW  

Rationale: mathematical weights / normalization (`canonical_0_100_v1`) unchanged. Semantic change of *which evidence is eligible* is represented by `input_selection_policy_version`, not a silent formula bump. Reproducibility requires both formula version **and** input selection policy version.

Option B (1.3 / 2.2.0) rejected for this sprint because the registry already surfaces the input-set change without implying a weight change.
