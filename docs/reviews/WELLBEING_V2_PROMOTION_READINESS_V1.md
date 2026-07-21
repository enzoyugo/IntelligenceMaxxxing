# WELLBEING V2 PROMOTION READINESS V1

## Lifecycle (unchanged)

| Formula | Version | Status |
|---------|---------|--------|
| wellbeing_v1 | 1.2 | **ACTIVE** |
| wellbeing_v2 | 2.1.0 | **SHADOW** |

## Why V1 remains ACTIVE

V2 has richer structure (acute/chronic/anticipatory, fingerprints, change state), but lacks longitudinal validation against personal outcomes. Isolation/input-selection fixes evidence quality for both; they do **not** authorize promotion.

## Proposed promotion gates

### Minimum data

| Gate | Threshold |
|------|-----------|
| Initial calibration eligibility | ≥ 20 labels |
| Promotion evaluation eligibility | ≥ 50 labels |

Require temporal coverage and state variety (not raw count alone).

### Prediction error

Compare V2 vs V1 on held-out personal labels:

- Happiness MAE / RMSE  
- Stress MAE / RMSE  
- Directional accuracy (rise / fall / stable)

### Warning quality

Precision, recall, false positives/negatives, median lead time.

### Confidence calibration

Higher confidence → lower error; plausible-range coverage; calibration by confidence band.

### Robustness

Missing domains, absent schedule, no check-in days, duplicate events, offline, alternate windows, weekday vs weekend.

### User utility

Useful / not useful / irrelevant / annoying / too late — collected in Shadow Lab feedback.

## Promotion rule

V2 may be **evaluated** for ACTIVE only when:

1. It beats V1 on real error metrics  
2. No critical metric regresses significantly  
3. Confidence is calibrated  
4. Alerts are useful  
5. Sample sufficiency gates pass  
6. User utility validates  
7. A formal versioned decision record is written  

**No auto-promotion.** This document does not change lifecycle status.
