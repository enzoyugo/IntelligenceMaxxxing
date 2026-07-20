# Wellbeing Calibration Policy V2

| Field | Value |
|---|---|
| **Formula** | `wellbeing_v2@2.0.0` |
| **Default state** | `UNCALIBRATED` |
| **Auto-calibration** | Forbidden without explicit gate passage |

## Objective

Adjust **personal offset and scale** (and optionally bounded weight nudges) so published scores align with user feedback labels—without opaque online learning, temporal leakage, or overwriting historical snapshots.

## Label requirements

Feedback must include:

- User perceived happiness (1–10 or mapped 0–100)
- User perceived stress (1–10 or mapped 0–100)
- `score_snapshot_id` referencing the Engine snapshot being rated
- Timestamp of label creation

Labels are stored append-only; never mutate past feedback rows.

## Temporal separation (leakage prevention)

| Rule | Requirement |
|---|---|
| Label horizon | Label timestamp must be **≥ 24h after** the `period_end` of the rated snapshot |
| Feature cutoff | Calibration fit uses only snapshots with `computed_at` strictly before label timestamp |
| Same-day exclusion | Same-calendar-day label + snapshot pairs are excluded from fit (even if ≥ 24h apart) |
| Future data | Features with `global_position` after snapshot `as_of_global_position` are forbidden |

## Sample gates

| Label count (valid pairs) | Calibration mode | Allowed adjustments |
|---|---|---|
| **< 7** | `NONE` | Global expert weights only; offset = 0, scale = 1 |
| **7–19** | `OFFSET` | Per-score affine offset: `score' = score + β_h`, `stress' = stress + β_s` |
| **20–49** | `OFFSET_SCALE` | Affine: `score' = α * score + β` with α ∈ [0.85, 1.15] |
| **50–99** | `OFFSET_SCALE_WEIGHT_NUDGE` | Above + sub-score weights may deviate ≤ **10%** from global with L2 penalty λ = 0.20 |
| **≥ 100** | `FULL_PERSONAL` | Weights may deviate ≤ **20%** with λ = 0.15; requires validation MAE beat V1 |

Between gates, the **highest eligible mode** applies (monotonic).

## Regularization toward global weights

Personal weight vector **w** is fit by minimizing:

```text
loss = MAE(labels, predictions) + λ * ||w - w_global||²
```

| Gate | λ |
|---|---:|
| 50–99 | 0.20 |
| ≥ 100 | 0.15 |

Global weights **w_global** are exactly `registry.HAPPINESS_WEIGHTS`, `registry.STRESS_WEIGHTS`. No unregularized personal fits permitted.

Offset/scale parameters use ridge α = 1.0 on β and log-scale deviation for α.

## Calibration status field

| Status | Meaning |
|---|---|
| `UNCALIBRATED` | < 20 labels; calibration component uses 0.5 prior |
| `CALIBRATED_OFFSET` | ≥ 20 labels, offset-only or offset+scale active |
| `CALIBRATED_FULL` | ≥ 100 labels with weight nudge, validation passed |

## Fit cadence

- Re-fit at most **once per 7 days** per user
- Minimum **3 new labels** since last fit to trigger refresh
- Fit runs asynchronously; snapshots store `calibration_applied_at` and parameter hash

## Rollback

| Trigger | Action |
|---|---|
| 14-day rolling MAE regresses > **15%** vs pre-calibration baseline | Revert to previous parameter set |
| User feedback `rating = inaccurate` on ≥ 3 consecutive snapshots | Suspend personal weights; revert to `OFFSET` only |
| Validation harness flags leakage on re-fit | Hard revert to global weights; mark `calibration_status = UNCALIBRATED` |
| Formula version bump | All personal parameters invalidated; cold-start recalibration |

Rollback is append-only: prior parameter sets remain in audit table for replay.

## Forbidden

- Single-label weight updates
- Training on future snapshots relative to label
- Modifying stored historical snapshot scores (recalculation produces new snapshot rows)
- Using LLM-extracted labels
- Calibrating confidence upward without label MAE improvement

## Version history

| Version | Change |
|---|---|
| 2.0.0 | Initial gated calibration policy |
