# WELLBEING CLEAN V1/V2 SNAPSHOT POST DEVICE FLOW V1

**Status:** PASS — real iPhone Daily Flow ingested; clean V1/V2 scores with sample 1.

## Preserved historical snapshots (do not mutate)

| Role | Snapshot ID | Formula |
|---|---|---|
| Prior V1 (post smoke exclusion, activation still counted) | `wbs_bb59f9a93c5e4f34bdea2d23e618f0dd` | `wellbeing_v1@1.2` ACTIVE |
| Prior V2 | `wbs_cce102a415584418b23766954f72871b` | `wellbeing_v2@2.1.0` SHADOW |

## New clean snapshots (activation cohort excluded)

Generated 2026-07-21T23:04:17Z via `scripts/audit/wellbeing_generate_effective_snapshots.py`.

### V1 ACTIVE

| Field | Value |
|---|---|
| Snapshot ID | `wbs_89b49a1b94eb49189509862d3c5b70b9` |
| Formula | `wellbeing_v1@1.2` ACTIVE |
| Happiness | null |
| Stress | null |
| Confidence | null |
| Sample days | 0 |
| Data sufficiency | `COLD_START` |
| Input selection policy | `wellbeing_input_selection_v1` |
| Included observations | 0 |
| Excluded test | 6 |
| Excluded invalidated | 1 |
| Excluded ambiguous | 0 |
| Input fingerprint | null |

### V2 SHADOW

| Field | Value |
|---|---|
| Snapshot ID | `wbs_c8c410258ec64745ba3b302dfedfd7dc` |
| Formula | `wellbeing_v2@2.1.0` SHADOW |
| Happiness | null |
| Stress | null |
| Overall confidence | 18.44 |
| Sample days | 0 |
| Data sufficiency | `COLD_START` |
| Change state | `INSUFFICIENT_EVIDENCE` |
| Input selection policy | `wellbeing_input_selection_v1` |
| Included observations | 0 |
| Excluded test | 6 |
| Excluded invalidated | 1 |
| Input fingerprint | `5273c2dafd37fd70aad22e4a62798f0c` |

## Honest-null decision

No Happiness/Stress invented. V2 confidence at cold start is formula output under insufficient evidence — not a fabricated Happiness/Stress axis. V2 remains SHADOW; not promoted.

## After real iPhone Daily Flow

| Field | Value |
|---|---|
| Engine observation ID | `obs_58f4c210426a4e34bf3e74b9d9e3255c` |
| Global position | 17 |
| Input classification | `INCLUDED` |
| New V1 snapshot ID | `wbs_8b1d679914d5430eb6d763d080150950` |
| V1 Happiness / Stress / Confidence / sample | 72.37 / 44.44 / 25 / 1 |
| V2 | SHADOW `@2.1.0` · H 69.14 · S 53.1 · C 28 · n=1 |
| Personal included / excl test / excl inval | 1 / 6 / 1 |

## Constraints honored

- No formula/weight changes
- No V2 promotion
- No ledger deletes
- Historical snapshot IDs preserved
- Smoke exclusion correction retained
