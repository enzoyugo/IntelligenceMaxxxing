# Wellbeing Canonical Normalization V1

## Version

`canonical_0_100_v1`

Applied once in `resolve_score_fields` / `extract_*` before V1/V2 formulas.

## Conversions

| Declared scale | Formula |
|----------------|---------|
| `0_100` | `normalized = raw` |
| `1_10` | `normalized = (raw - 1) / 9 * 100` |

Likert semantics: **1 → 0**, **10 → 100**.

## Double-normalization guard

`CheckInDay` / `DayRecord` store canonical 0–100 only. `compute_wellbeing_v1` does not re-scale. V2 `scale_0_100` maps 0–100 → composition signal `[-1,1]`.

## Formula versions

| Formula | Version | Status | Why |
|---------|---------|--------|-----|
| `wellbeing_v1` | `1.2` | ACTIVE | Removes magnitude heuristic of `1.1` |
| `wellbeing_v2` | `2.1.0` | SHADOW | Canonical 0–100 inputs (was Likert-assumed `2.0.0`) |

Weights unchanged. Historical snapshots for `1.0` / `1.1` / `2.0.0` preserved (new compute → new snapshot IDs).

## Snapshot metadata (features)

- `measurement_contract_version`
- `input_normalization_version`
- `explicit_scale_ratio` / `legacy_scale_ratio`
- `ambiguous_scale_count` / `invalid_measurement_count`
- `scale_resolution_summary`
