# Wellbeing V1 Score Saturation Root Cause V1

**Date:** 2026-07-20  
**Snapshot audited (pre-fix):** `wbs_48c34483c12b41f3afde33a10c18f678` / later `wbs_ff49d798…`  
**Observed:** Happiness 100 · Stress 100 · Confidence 98.4 · PARTIAL · 5 days

## Snapshot / raw inputs

Live check-in means in `features.avg_*_raw` were ~0–100 (e.g. happiness ≈ 62–70, stress ≈ 35–40), matching LifeOS Daily Flow storage.

## Input scales

| Layer | Assumed |
|---|---|
| Unit tests / V1.0 scaler | 1–10 Likert |
| Live LifeOS attributes | 0–100 |
| V1.0 `_scale_1_10_to_100` | Treats any value ≥10 as saturated → 100 |

## Normalized / intermediate / clamp

V1.0: `base = (raw-1)/9*100` then clamp → for raw=66 → **100** before composition.  
Energy/productivity similarly saturated → agency Confidence ≈ 98.

## Confidence components (V1.0)

Agency blend: 0.45·prod + 0.30·energy + 0.15·gym + 0.10·stability — **not** sample maturity. Misread as epistemic confidence in UI.

## Duplicate analysis

`extract_checkin_days` first-write-wins per calendar day. Idempotent replay does **not** double-count.

## Root cause

**Scale contract mismatch:** 0–100 Daily Flow values passed through a 1–10 scaler that hard-clamps at ≥10 → Happiness/Stress 100; Confidence≈98 was agency, uncapped by n=5 / PARTIAL.

## Fix

`wellbeing_v1@1.1`:

- `_to_score_100`: ≤10 → Likert; >10 → already 0–100; normalize once; clamp at end
- `confidence` = epistemic (coverage + domains + sufficiency + uncalibrated dampener + sample maturity caps)
- `features.agency_score` preserves former agency composite
- `EXTREME_SCORE_LOW_EVIDENCE` when extremes under thin evidence
- V2 remains SHADOW; V1 stays ACTIVE

## Formula version

| Before | After |
|---|---|
| `wellbeing_v1@1.0` | `wellbeing_v1@1.1` |

## Post-fix live (same observation set)

Happiness **69.45** · Stress **38.0** · Confidence **45.0** (cap) · PARTIAL · n=5 · missing `schedule`

## Regression tests

`tests/unit/test_wellbeing_v1_scale_sanity.py`, updated `test_wellbeing_v1.py`
